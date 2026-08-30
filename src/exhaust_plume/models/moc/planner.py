"""Planning and audit wrappers for the isolated planar-MOC chain lane.

The chain solvers own numerical acceptance.  This module owns the lightweight
planner view used by validation and research orchestration: it records every
incoming handoff before a callback is invoked and preserves the solver's
typed termination decision.  The prescribed-boundary mode is an executable
mock only; it cannot raise a cell's fidelity or closure claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Any, Callable, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainResult,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCellClosureStatus,
  MocCellContinuationSolver,
  MocChainGeometryFidelity,
  continue_moc_cell_chain,
)
from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceStatus,
  MocReflectedDomainAlternatingPhysicalFieldResult,
  MocReflectedDomainAlternatingPhysicalFieldStatus,
  MocReflectedDomainAlternatingSourceResult,
  MocReflectedDomainRemeshResult,
  MocReflectedDomainSolverOwnedFirstCellResult,
  MocReflectedDomainGlobalShockRemeshResult,
  solve_reflected_domain_solver_owned_first_cell,
  solve_reflected_domain_global_shock_remesh,
  solve_reflected_domain_alternating_physical_field,
  solve_reflected_domain_alternating_source,
)
from exhaust_plume.models.moc.caustic_bridge import (
  MocCausticBridgeSide,
  MocCausticBridgeStatus,
  MocCausticUpstreamBridge,
)
from exhaust_plume.models.moc.caustic_continuation import (
  MocCausticUpstreamContinuationResult,
  MocCausticUpstreamContinuationStatus,
  solve_caustic_upstream_continuation,
)
from exhaust_plume.models.moc.caustic_remesh import (
  MocCausticShockRemeshRequest,
  MocCausticShockRemeshResult,
  solve_caustic_shock_remesh,
  solve_caustic_shock_remesh_from_upstream_bridge,
)
from exhaust_plume.models.moc.caustic_upstream_remesh import (
  MocCausticUpstreamRemeshResult,
)
from exhaust_plume.models.moc.caustic_terminal import (
  solve_caustic_simple_wave_terminal_remesh,
)
from exhaust_plume.models.moc.physical_cell import (
  MocAmbientClosedPostShockChainCandidate,
  MocPhysicalPostShockFieldContinuationSolve,
  MocPhysicalPostShockFieldResult,
  MocPhysicalPostShockTerminalPatchTransitionResult,
  solve_ambient_closed_post_shock_chain_cell_from_candidate_or_termination,
  solve_ambient_closed_post_shock_chain_cell_from_terminal_reflection_patch_ambient_closure_or_termination,
  solve_ambient_closed_post_shock_terminal_patch_transition,
  continue_ambient_closed_post_shock_chain,
)
from exhaust_plume.models.moc.first_cell_closure import (
  MocFirstCellTerminalClosureResult,
)
from exhaust_plume.models.moc.first_cell_candidate import (
  MocFirstCellCandidateResult,
)
from exhaust_plume.models.moc.first_cell_free_boundary import (
  MocFirstCellFreeBoundaryCorrectionResult,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPostShockCharacteristicZoneResult,
  MocPostShockFieldContinuationSolver,
  assemble_post_shock_characteristic_field,
  continue_post_shock_characteristic_chain,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  fit_euler_consistent_shock_boundary,
)
from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerCompanionFieldResult,
  assemble_euler_consistent_companion_characteristic_strip,
)
from exhaust_plume.models.moc.euler_ambient_field import (
  MocEulerAmbientShockFieldResult,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeRemeshResult,
  remesh_euler_ambient_first_wedge,
)
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicResult,
  MocEulerAmbientFirstWedgeCharacteristicFieldResult,
  solve_euler_ambient_first_wedge_characteristic_remesh,
  remesh_euler_ambient_first_wedge_characteristic_field,
)
from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  solve_euler_ambient_first_wedge_entropy_carry,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_field,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_coupling import (
  solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling,
)
from exhaust_plume.models.moc.euler_entropy_refinement import (
  MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
  refine_euler_ambient_first_wedge_entropy_carry,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.models.moc.euler_post_shock import (
  MocEulerPostShockFieldResult,
  assemble_euler_post_shock_field,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeControlSection,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFreeBoundaryResult,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  run_mixed_regime_closure_solver,
  solve_mixed_regime_downstream_perimeter,
  solve_mixed_regime_downstream_free_boundary,
  solve_mixed_regime_downstream_free_boundary_from_control_section,
)
from exhaust_plume.models.moc.mixed_regime_entropy import (
  MocMixedRegimeEntropyHandoffResult,
)
from exhaust_plume.models.moc.mixed_regime_entropy_transport import (
  MocMixedRegimeEntropyTransportResult,
  solve_mixed_regime_entropy_transport_boundary,
)
from exhaust_plume.models.moc.mixed_regime_planar import (
  MocMixedRegimePlanarFieldSolver,
  MocMixedRegimePlanarPotentialReference,
  MocMixedRegimePlanarFrozenProfileReference,
  MocMixedRegimePlanarSolveResult,
  run_mixed_regime_planar_field_solver,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripCausticShockSeedResult,
  MocSourceStripContinuationResult,
  MocSourceStripContinuationStatus,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
)
from exhaust_plume.models.moc.coupled import (
  MocAmbientPhysicalFieldStatus,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_chain_cell,
  solve_marched_attached_shock_from_caustic_upstream_bridge,
  solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary,
  solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination,
  solve_marched_attached_shock_chain_cell_from_post_shock_field_with_invariant_boundary_or_termination,
  solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination,
  solve_marched_attached_shock_chain_cell_from_source_strip_or_termination,
)
from exhaust_plume.models.moc.family_band_solver import (
  MocCausticFamilyBandEnvelopeStatus,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination,
  trace_caustic_family_band_forward_envelope,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocChainPlannerKind',
  'MocAmbientClosedChainSourceMode',
  'MocChainPlannerStep',
  'MocChainPlannerResult',
  'MocEulerCompanionFieldContinuationSolve',
  'MocEulerCompanionFieldChainStep',
  'MocEulerCompanionFieldChainPlannerResult',
  'MocEulerAmbientShockFieldContinuationSolve',
  'MocEulerAmbientShockFieldChainStep',
  'MocEulerAmbientShockFieldChainPlannerResult',
  'MocEulerAmbientShockFieldPlannerResult',
  'MocFirstCellTerminalClosurePlannerResult',
  'MocFirstCellFreeBoundaryCorrectionPlannerResult',
  'MocFirstCellResearchChainPlannerResult',
  'MocCausticUpstreamContinuationPlannerResult',
  'MocPrescribedMixedRegimeClosureMock',
  'MocSolverGeneratedMixedRegimeClosureReference',
  'MocPrescribedPostShockChainMock',
  'MocSolverGeneratedPostShockChainReference',
  'MocFieldCoupledPostShockChainReference',
  'MocBoundedUpstreamFieldSource',
  'build_terminal_reflection_patch_upstream_source',
  'MocSolverGeneratedAmbientClosedPostShockChainReference',
  'MocTerminalReflectionPatchAmbientClosureChainReference',
  'plan_reflected_domain_remesh_ambient_closed_chain',
  'MocPrescribedAmbientClosedPostShockChainMock',
  'MocPhysicalPostShockTerminalPatchPlannerResult',
  'MocAmbientClosedPostShockChainTerminalPlannerResult',
  'plan_moc_chain',
  'plan_euler_companion_field_chain',
  'MocEulerCompanionFieldChainMock',
  'plan_euler_companion_field_chain_mock',
  'plan_euler_ambient_shock_field_reference',
  'plan_euler_ambient_shock_field_chain',
  'MocEulerAmbientShockFieldChainMock',
  'plan_euler_ambient_shock_field_chain_mock',
  'MocEulerAmbientFirstWedgeRemeshPlannerStep',
  'MocEulerAmbientFirstWedgeRemeshPlannerResult',
  'plan_euler_ambient_first_wedge_remesh_mock',
  'MocEulerAmbientFirstWedgeCharacteristicPlannerStep',
  'MocEulerAmbientFirstWedgeCharacteristicPlannerResult',
  'plan_euler_ambient_first_wedge_characteristic_remesh',
  'MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep',
  'MocEulerAmbientFirstWedgeCharacteristicFieldPlannerResult',
  'plan_euler_ambient_first_wedge_characteristic_field',
  'MocEulerAmbientFirstWedgeEntropyCarryPlannerStep',
  'MocEulerAmbientFirstWedgeEntropyCarryPlannerResult',
  'plan_euler_ambient_first_wedge_entropy_carry',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerResult',
  'plan_euler_ambient_first_wedge_entropy_characteristic_field',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock',
  'plan_euler_ambient_first_wedge_entropy_characteristic_field_chain',
  'plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock',
  'plan_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_probe',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerResult',
  'plan_euler_ambient_first_wedge_entropy_carry_refinement',
  'MocEulerPostShockFieldContinuationSolve',
  'MocEulerPostShockFieldChainStep',
  'MocEulerPostShockFieldChainPlannerResult',
  'MocEulerPostShockFieldChainMock',
  'plan_euler_post_shock_field_chain',
  'plan_euler_post_shock_field_chain_mock',
  'plan_post_shock_characteristic_chain',
  'plan_post_shock_field_chain',
  'plan_source_strip_shock_chain',
  'plan_source_strip_shock_chain_sequence',
  'plan_post_shock_field_invariant_chain',
  'plan_prescribed_post_shock_chain_mock',
  'plan_solver_generated_post_shock_chain_reference',
  'plan_field_coupled_post_shock_chain_reference',
  'plan_solver_generated_ambient_closed_post_shock_chain_reference',
  'plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure',
  'plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_mixed_regime',
  'plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_planar_handoff',
  'plan_prescribed_ambient_closed_post_shock_chain_mock',
  'plan_first_cell_geometry_owned_research_chain',
  'plan_terminal_reflection_patch_chain',
  'plan_post_shock_zone_chain',
  'plan_caustic_family_band_chain',
  'plan_caustic_family_band_invariant_chain',
  'plan_caustic_origin_envelope_chain',
  'plan_caustic_upstream_bridge_chain',
  'plan_caustic_upstream_bridge_invariant_chain',
  'plan_caustic_upstream_continuation',
  'plan_caustic_shock_remesh_chain',
  'plan_caustic_shock_remesh_chain_from_upstream_bridge',
  'plan_caustic_upstream_remesh_shock_chain',
  'plan_caustic_upstream_remesh_shock_chain_sequence',
  'plan_reflected_domain_remesh_shock_chain',
  'plan_reflected_domain_remesh_shock_chain_sequence',
  'plan_reflected_domain_alternating_source_chain',
  'plan_reflected_domain_alternating_source_chain_sequence',
  'plan_reflected_domain_alternating_source_chain_from_physical_field',
  'plan_reflected_domain_solver_owned_first_cell_chain',
  'plan_first_cell_geometry_owned_alternating_research_chain',
  'plan_caustic_simple_wave_terminal_chain',
  'plan_caustic_remesh_downstream_field_chain',
  'plan_caustic_remesh_downstream_field_invariant_chain',
  'plan_ambient_pressure_field_chain',
  'plan_ambient_closed_post_shock_chain',
  'plan_ambient_closed_post_shock_chain_terminal_patch',
  'plan_ambient_closed_post_shock_chain_terminal_patch_with_mixed_regime',
  'plan_ambient_closed_post_shock_chain_terminal_patch_with_planar_handoff',
  'plan_ambient_closed_post_shock_chain_terminal_patch_mock',
  'plan_ambient_closed_post_shock_chain_terminal_patch_reference',
  'plan_first_cell_terminal_closure',
  'plan_first_cell_free_boundary_correction',
  'plan_prescribed_first_cell_terminal_closure_mock',
  'plan_solver_generated_first_cell_terminal_closure_reference',
  'plan_solver_generated_first_cell_terminal_closure_reference_from_control_section',
  'plan_solver_generated_first_cell_terminal_closure_reference_from_control_section_flux',
  'plan_first_cell_terminal_closure_with_planar_handoff',
  'plan_first_cell_terminal_closure_with_planar_potential_reference',
  'plan_first_cell_terminal_closure_with_planar_frozen_profile_reference',
)


class MocChainPlannerKind(str, Enum):
  """Provenance label for a planner run."""

  PRESCRIBED_BOUNDARY_MOCK = 'prescribed-boundary-mock'
  SOLVER_GENERATED_REFERENCE = 'solver-generated-reference'
  UPSTREAM_COUPLED_RESEARCH = 'upstream-coupled-research'
####


class MocAmbientClosedChainSourceMode(str, Enum):
  """Solver-owned source choices for an ambient-closed chain reference.

  ``PREVIOUS_FIELD`` preserves the original bounded-domain behavior: the
  accepted field itself is exposed as the next upstream source and a
  downstream miss is a typed field-boundary stop.  ``TERMINAL_REFLECTION_PATCH``
  derives the next bounded source by projecting the accepted field's terminal
  shock/ambient strip to its reflected centerline patch.  The latter is a
  real solver-owned continuation attempt, but it remains research-only until
  the reflected-domain and downstream free-boundary gates are independently
  closed.
  """

  PREVIOUS_FIELD = 'previous-ambient-closed-physical-field'
  TERMINAL_REFLECTION_PATCH = 'terminal-reflection-patch'
####


@dataclass(frozen=True, slots=True)
class MocChainPlannerStep:
  """One callback invocation and the exact handoff it was given."""

  current_cell_index: int
  next_cell_index: int
  current_end_x_m: float
  boundary_kind: MocChainBoundaryKind | None
  incoming_handoff_sample_count: int
  incoming_total_pressure_range_Pa: tuple[float, float] | None
  incoming_handoff_fingerprint: str | None = None
  incoming_handoff_link_verified: bool | None = None
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_end_x_m: float | None = None
  result_geometry_fidelity: MocChainGeometryFidelity | None = None
  result_physical_closure: MocCellClosureStatus | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None
  result_boundary_kind: MocChainBoundaryKind | None = None
  result_handoff_sample_count: int | None = None
  result_total_pressure_range_Pa: tuple[float, float] | None = None
  result_handoff_fingerprint: str | None = None
  result_consumed_handoff_sample_count: int | None = None
  result_consumed_total_pressure_range_Pa: tuple[float, float] | None = None
  result_consumed_handoff_fingerprint: str | None = None

  def __post_init__(self) -> None:
    if isinstance(self.current_cell_index, bool) or self.current_cell_index < 1:
      raise ValueError('current_cell_index must be a positive integer')
    if isinstance(self.next_cell_index, bool) or self.next_cell_index != self.current_cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current_cell_index')
    if not isfinite(float(self.current_end_x_m)):
      raise ValueError('current_end_x_m must be finite')
    if self.boundary_kind is not None and not isinstance(
        self.boundary_kind,
        MocChainBoundaryKind,
    ):
      raise TypeError('boundary_kind must be a MocChainBoundaryKind or None')
    if isinstance(self.incoming_handoff_sample_count, bool) or self.incoming_handoff_sample_count < 0:
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    pressure_range = self.incoming_total_pressure_range_Pa
    if pressure_range is not None:
      if len(pressure_range) != 2:
        raise ValueError('incoming_total_pressure_range_Pa must contain two values')
      minimum, maximum = (float(value) for value in pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError('incoming total-pressure range must be finite and ordered')
      object.__setattr__(self, 'incoming_total_pressure_range_Pa', (minimum, maximum))
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    if self.result_status is not None and not isinstance(self.result_status, str):
      raise TypeError('result_status must be a string or None')
    if self.result_end_x_m is not None and not isfinite(float(self.result_end_x_m)):
      raise ValueError('result_end_x_m must be finite when supplied')
    if self.result_geometry_fidelity is not None and not isinstance(
        self.result_geometry_fidelity,
        MocChainGeometryFidelity,
    ):
      raise TypeError(
        'result_geometry_fidelity must be a MocChainGeometryFidelity or None'
      )
    if self.result_physical_closure is not None and not isinstance(
        self.result_physical_closure,
        MocCellClosureStatus,
    ):
      raise TypeError(
        'result_physical_closure must be a MocCellClosureStatus or None'
      )
    if self.result_termination_reason is not None and not isinstance(
        self.result_termination_reason,
        MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
        self.result_physical_termination,
        bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')
    if self.incoming_handoff_link_verified is not None and not isinstance(
        self.incoming_handoff_link_verified,
        bool,
    ):
      raise TypeError('incoming_handoff_link_verified must be a bool or None')
    if self.result_boundary_kind is not None and not isinstance(
        self.result_boundary_kind,
        MocChainBoundaryKind,
    ):
      raise TypeError('result_boundary_kind must be a MocChainBoundaryKind or None')
    if self.result_handoff_sample_count is not None:
      if (
        isinstance(self.result_handoff_sample_count, bool)
        or self.result_handoff_sample_count < 0
      ):
        raise ValueError('result_handoff_sample_count must be nonnegative when supplied')
    result_pressure_range = self.result_total_pressure_range_Pa
    if result_pressure_range is not None:
      if len(result_pressure_range) != 2:
        raise ValueError('result_total_pressure_range_Pa must contain two values')
      minimum, maximum = (float(value) for value in result_pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError('result total-pressure range must be finite and ordered')
      object.__setattr__(self, 'result_total_pressure_range_Pa', (minimum, maximum))
    if self.result_handoff_fingerprint is not None and not isinstance(
        self.result_handoff_fingerprint,
        str,
    ):
      raise TypeError('result_handoff_fingerprint must be a string or None')
    if self.result_consumed_handoff_sample_count is not None:
      if (
        isinstance(self.result_consumed_handoff_sample_count, bool)
        or self.result_consumed_handoff_sample_count < 0
      ):
        raise ValueError(
          'result_consumed_handoff_sample_count must be nonnegative when supplied'
        )
    consumed_pressure_range = self.result_consumed_total_pressure_range_Pa
    if consumed_pressure_range is not None:
      if len(consumed_pressure_range) != 2:
        raise ValueError(
          'result_consumed_total_pressure_range_Pa must contain two values'
        )
      minimum, maximum = (float(value) for value in consumed_pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError(
          'result consumed total-pressure range must be finite and ordered'
        )
      object.__setattr__(
        self,
        'result_consumed_total_pressure_range_Pa',
        (minimum, maximum),
      )
    if self.result_consumed_handoff_fingerprint is not None and not isinstance(
        self.result_consumed_handoff_fingerprint,
        str,
    ):
      raise TypeError(
        'result_consumed_handoff_fingerprint must be a string or None'
      )
  ####

  @classmethod
  def from_boundary(
    cls,
    current: MocChainCell,
    next_cell_index: int,
    boundary: tuple[MocChainBoundarySample, ...],
    *,
    previous_result_handoff_fingerprint: str | None = None,
  ) -> 'MocChainPlannerStep':
    pressure_range = None
    if boundary:
      pressures = tuple(sample.total_pressure_Pa for sample in boundary)
      pressure_range = (min(pressures), max(pressures))
    incoming_fingerprint = _handoff_fingerprint(boundary)
    return cls(
      current_cell_index=current.cell_index,
      next_cell_index=next_cell_index,
      current_end_x_m=current.end_x_m,
      boundary_kind=(
        current.continuation_boundary_kind if boundary else None
      ),
      incoming_handoff_sample_count=len(boundary),
      incoming_total_pressure_range_Pa=pressure_range,
      incoming_handoff_fingerprint=incoming_fingerprint,
      incoming_handoff_link_verified=(
        None
        if previous_result_handoff_fingerprint is None
        else incoming_fingerprint is not None
        and incoming_fingerprint == previous_result_handoff_fingerprint
      ),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'current_cell_index': self.current_cell_index,
      'next_cell_index': self.next_cell_index,
      'current_end_x_m': self.current_end_x_m,
      'boundary_kind': None if self.boundary_kind is None else self.boundary_kind.value,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_total_pressure_range_Pa': self.incoming_total_pressure_range_Pa,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_end_x_m': self.result_end_x_m,
      'result_geometry_fidelity': (
        None
        if self.result_geometry_fidelity is None
        else self.result_geometry_fidelity.value
      ),
      'result_physical_closure': (
        None
        if self.result_physical_closure is None
        else self.result_physical_closure.value
      ),
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
      'result_boundary_kind': (
        None
        if self.result_boundary_kind is None
        else self.result_boundary_kind.value
      ),
      'result_handoff_sample_count': self.result_handoff_sample_count,
      'result_total_pressure_range_Pa': self.result_total_pressure_range_Pa,
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
      'result_consumed_handoff_sample_count': self.result_consumed_handoff_sample_count,
      'result_consumed_total_pressure_range_Pa': (
        self.result_consumed_total_pressure_range_Pa
      ),
      'result_consumed_handoff_fingerprint': self.result_consumed_handoff_fingerprint,
    }
  ####

  def with_solver_result(self, result: object) -> 'MocChainPlannerStep':
    """Attach the typed result returned for this planned handoff."""

    if isinstance(result, MocChainTerminationDecision):
      return replace(
        self,
        result_kind='termination-returned',
        result_status=result.reason.value,
        result_termination_reason=result.reason,
        result_physical_termination=result.physical_termination,
      )
    if isinstance(result, MocPostShockChainCellSolve):
      field = result.field
      consumed_boundary = _field_incoming_handoff(field)
      boundary = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          field.continuation_boundary_states,
          field.continuation_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      return replace(
        self,
        result_kind='field-solve-returned',
        result_status=field.status.value,
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=(
          MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
          if field.converged
          else None
        ),
        result_physical_closure=(
          MocCellClosureStatus.CLOSED
          if field.physical_closure_verified
          else MocCellClosureStatus.OPEN
        ),
        **_result_handoff_fields(
          boundary,
          MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER,
        ),
        **_result_consumed_handoff_fields(consumed_boundary),
      )
    if isinstance(result, MocPhysicalPostShockFieldContinuationSolve):
      field = result.field
      consumed_boundary = _field_incoming_handoff(field)
      boundary = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          field.centerline_boundary_states,
          field.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      return replace(
        self,
        result_kind='physical-field-solve-returned',
        result_status=field.status.value,
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=(
          MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
          if field.physical_closure_verified
          else None
        ),
        result_physical_closure=(
          MocCellClosureStatus.CLOSED
          if field.physical_closure_verified
          else MocCellClosureStatus.OPEN
        ),
        **_result_handoff_fields(
          boundary,
          MocChainBoundaryKind.CENTERLINE_TRACE,
        ),
        **_result_consumed_handoff_fields(consumed_boundary),
      )
    if isinstance(result, MocChainCell):
      return replace(
        self,
        result_kind='cell-returned',
        result_status='resolved' if result.resolved else 'unresolved',
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=result.geometry_fidelity,
        result_physical_closure=result.physical_closure,
        **_result_handoff_fields(
          result.continuation_boundary,
          result.continuation_boundary_kind,
        ),
      )
    if result is None:
      return replace(
        self,
        result_kind='no-cell-returned',
        result_status='none',
      )
    return replace(
      self,
      result_kind='invalid-result-returned',
      result_status=type(result).__name__,
    )
  ####

  def with_solver_error(self, error: BaseException) -> 'MocChainPlannerStep':
    """Record a callback exception before the chain converts it to failure."""

    return replace(
      self,
      result_kind='solver-error',
      result_status=type(error).__name__,
    )
  ####


def _handoff_fingerprint(
  boundary: tuple[MocChainBoundarySample, ...],
) -> str | None:
  """Return a deterministic audit fingerprint for an exact typed handoff.

  The digest is provenance bookkeeping, not a physical validation result.  It
  lets a serialized planner report identify the full state/pressure boundary
  that was presented to a callback without duplicating every sample in the
  report.  ``float.hex`` keeps the representation deterministic across JSON
  serialization and preserves signed zero when it is present.
  """

  if not boundary:
    return None
  payload = '\n'.join(
    '|'.join(
      (
        state_value.hex()
        for state_value in (
          sample.state.x_m,
          sample.state.y_m,
          sample.state.theta_rad,
          sample.state.mach,
          sample.state.gamma,
          sample.total_pressure_Pa,
        )
      )
    )
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()


def _euler_entropy_characteristic_field_fingerprint(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> str:
  """Return a deterministic identity for an internal entropy field.

  This is provenance bookkeeping for the research-chain planner.  It includes
  the solver status, raw node states/pressures, and topology-bearing cell
  vertices so a serialized continuation step cannot be mistaken for a
  handoff from a different field.
  """

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = [
    f'status:{field.status.value}',
    f'boundary-kind:{field.continuation_boundary_kind.value}',
    f'boundary-indices:{field.continuation_boundary_node_indices!r}',
  ]
  payload.extend(
    f'node:{node.node_index}|{node.point_m[0].hex()}|'
    f'{node.point_m[1].hex()}|{state_payload(node.state)}|'
    f'{node.total_pressure_Pa.hex()}'
    for node in field.nodes
  )
  payload.append('cells')
  payload.extend(
    f'{cell.cell_index}|{cell.cell_kind}|' + '|'.join(
      value.hex() for point in cell.vertices_xr_m for value in point
    )
    for cell in field.cells
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()


def _euler_entropy_characteristic_field_x_extent(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> tuple[float, float] | None:
  """Return the axial extent of every retained internal-field node."""

  points = tuple(node.point_m for node in field.nodes)
  if not points:
    return None
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  return min(values), max(values)


def _euler_entropy_characteristic_field_local_gates_verified(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> bool:
  """Check the model-side local gates before a field enters a sequence."""

  return bool(
    field.converged
    and field.local_consistency_verified
    and field.topology.connected
    and field.topology.forms_closed_zone
    and field.topology.nonmanifold_edge_count == 0
    and field.pressure_lineage_verified
    and field.characteristic_geometry_verified
    and field.variable_entropy_compatibility_verified
    and field.cell_euler_residuals_finite
    and field.cell_euler_residuals_verified
    and field.internal_characteristic_closure_verified
    and field.continuation_boundary_verified
    and bool(field.continuation_boundary)
    and not field.physical_closure_verified
    and field.chain_promotion_blocked
    and not field.production_claim_allowed
  )


def _euler_companion_field_fingerprint(
  field: MocEulerCompanionFieldResult,
) -> str:
  """Return a deterministic identity for an open Euler field domain."""

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = [f'status:{field.status.value}']
  for label, states, pressures in (
    (
      'shock',
      field.shock_boundary_states,
      field.shock_boundary_total_pressure_Pa,
    ),
    (
      'companion',
      field.companion_boundary_states,
      field.companion_boundary_total_pressure_Pa,
    ),
    ('interior', field.interior_states, field.interior_total_pressure_Pa),
  ):
    payload.append(label)
    payload.extend(
      f'{state_payload(state)}|{pressure.hex()}'
      for state, pressure in zip(states, pressures, strict=True)
    )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()


def _euler_companion_field_x_extent(
  field: MocEulerCompanionFieldResult,
) -> tuple[float, float] | None:
  points = (
    *field.shock_boundary_points_m,
    *field.companion_boundary_points_m,
    *field.interior_points_m,
  )
  if not points:
    return None
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  return min(values), max(values)


def _translate_euler_companion_field(
  field: MocEulerCompanionFieldResult,
  offset_x_m: float,
) -> MocEulerCompanionFieldResult:
  """Translate one open field for the deterministic continuation mock.

  The helper rebuilds the translated strip through the real Euler
  characteristic assembler.  It is deliberately a planner fixture: the
  translated field is not a physical solution of the missing downstream
  boundary problem and its incoming frontier is recorded by the continuation
  wrapper rather than inferred as a new shock solve.
  """

  if not isinstance(field, MocEulerCompanionFieldResult):
    raise TypeError('field must be a MocEulerCompanionFieldResult')
  if field.shock_boundary is None:
    raise ValueError('field must retain its Euler shock boundary')
  offset = float(offset_x_m)
  if not isfinite(offset) or offset <= 0.0:
    raise ValueError('offset_x_m must be finite and positive')

  def translated_state(state: CharacteristicState) -> CharacteristicState:
    return replace(state, x_m=state.x_m + offset)

  shock_boundary = field.shock_boundary
  translated_shock = replace(
    shock_boundary,
    upstream_states=tuple(
      translated_state(state) for state in shock_boundary.upstream_states
    ),
    downstream_states=tuple(
      translated_state(state) for state in shock_boundary.downstream_states
    ),
    shock_points_m=tuple(
      (point[0] + offset, point[1])
      for point in shock_boundary.shock_points_m
    ),
  )
  companion = tuple(
    MocChainBoundarySample(
      state=translated_state(state),
      total_pressure_Pa=pressure,
    )
    for state, pressure in zip(
      field.companion_boundary_states,
      field.companion_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  return assemble_euler_consistent_companion_characteristic_strip(
    translated_shock,
    companion,
    position_tolerance_m=field.position_tolerance_m,
    invariant_tolerance=field.invariant_tolerance,
    pressure_tolerance=field.pressure_tolerance,
  )


def _euler_ambient_shock_field_fingerprint(
  field: MocEulerAmbientShockFieldResult,
) -> str:
  """Return a deterministic identity for an exact open shock-field result."""

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = [
    f'status:{field.status.value}',
    f'ambient-pressure:{field.ambient_pressure_Pa!r}',
  ]
  if field.shock_boundary is not None:
    payload.append('shock')
    payload.extend(
      f'{state_payload(state)}|{point[0].hex()}|{point[1].hex()}'
      for state, point in zip(
        field.shock_boundary.downstream_states,
        field.shock_boundary.shock_points_m,
        strict=True,
      )
    )
  if field.ambient_march is not None:
    payload.append('ambient')
    payload.extend(
      f'{state_payload(sample.state)}|{sample.point_m[0].hex()}|'
      f'{sample.point_m[1].hex()}|{sample.total_pressure_Pa.hex()}'
      for sample in field.ambient_march.boundary_samples
    )
  if field.ambient_companion_boundary is not None:
    payload.append('explicit-companion')
    payload.extend(
      f'{state_payload(sample.state)}|{sample.point_m[0].hex()}|'
      f'{sample.point_m[1].hex()}|{sample.total_pressure_Pa.hex()}'
      for sample in field.ambient_companion_boundary.samples
    )
  if field.attachment_wedge is not None:
    payload.append('attachment-wedge:' + field.attachment_wedge.status.value)
    payload.extend(
      f'{trial.plus_source_index}|{trial.minus_source_index}|'
      f'{trial.accepted}|{trial.forward_margin_m!r}'
      for trial in field.attachment_wedge.trials
    )
  if field.field is not None:
    payload.append('companion:' + _euler_companion_field_fingerprint(field.field))
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()


def _euler_ambient_shock_field_x_extent(
  field: MocEulerAmbientShockFieldResult,
) -> tuple[float, float] | None:
  """Return the x extent of every retained exact open-field boundary."""

  points: tuple[tuple[float, float], ...] = ()
  if field.shock_boundary is not None:
    points += tuple(field.shock_boundary.shock_points_m)
  if field.ambient_march is not None:
    points += tuple(field.ambient_march.points_m)
  if field.ambient_companion_boundary is not None:
    points += tuple(
      sample.point_m for sample in field.ambient_companion_boundary.samples
    )
  if field.field is not None:
    points += (
      *field.field.shock_boundary_points_m,
      *field.field.companion_boundary_points_m,
      *field.field.interior_points_m,
    )
  if not points:
    return None
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  return min(values), max(values)


def _euler_post_shock_field_fingerprint(
  field: MocEulerPostShockFieldResult,
) -> str:
  """Return a deterministic identity for a local post-shock field."""

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = [f'status:{field.status.value}']
  for label, points, states, pressures in (
    (
      'shock',
      field.shock_boundary_points_m,
      field.shock_boundary_states,
      field.shock_boundary_total_pressure_Pa,
    ),
    (
      'centerline',
      field.centerline_boundary_points_m,
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
    ),
  ):
    payload.append(label)
    payload.extend(
      f'{point[0].hex()}|{point[1].hex()}|{state_payload(state)}|{pressure.hex()}'
      for point, state, pressure in zip(points, states, pressures, strict=True)
    )
  payload.append('nodes')
  payload.extend(
    f'{node.point_m[0].hex()}|{node.point_m[1].hex()}|'
    f'{state_payload(node.state)}|{node.total_pressure_Pa!r}'
    for node in field.nodes
  )
  payload.append('cells')
  payload.extend(
    '|'.join(value.hex() for point in cell.vertices_xr_m for value in point)
    for cell in field.cells
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()


def _euler_post_shock_field_x_extent(
  field: MocEulerPostShockFieldResult,
) -> tuple[float, float] | None:
  """Return the retained local-field axial extent."""

  points = (
    *(point for cell in field.cells for point in cell.vertices_xr_m),
    *field.shock_boundary_points_m,
    *field.centerline_boundary_points_m,
  )
  if not points:
    return None
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  return min(values), max(values)


def _translate_euler_post_shock_field(
  field: MocEulerPostShockFieldResult,
  offset_x_m: float,
) -> MocEulerPostShockFieldResult:
  """Reassemble one local field on a fresh translated shock domain."""

  if not isinstance(field, MocEulerPostShockFieldResult):
    raise TypeError('field must be a MocEulerPostShockFieldResult')
  if not field.converged or field.shock_boundary is None:
    raise ValueError('field must be a converged local field with its shock boundary')
  offset = float(offset_x_m)
  if not isfinite(offset) or offset <= 0.0:
    raise ValueError('offset_x_m must be finite and positive')

  def translated_state(state: CharacteristicState) -> CharacteristicState:
    return replace(state, x_m=state.x_m + offset)

  shock = field.shock_boundary
  translated_shock = replace(
    shock,
    upstream_states=tuple(
      translated_state(state) for state in shock.upstream_states
    ),
    downstream_states=tuple(
      translated_state(state) for state in shock.downstream_states
    ),
    shock_points_m=tuple(
      (point[0] + offset, point[1])
      for point in shock.shock_points_m
    ),
  )
  return assemble_euler_post_shock_field(
    translated_shock,
    position_tolerance_m=field.position_tolerance_m,
    invariant_tolerance=field.invariant_tolerance,
    state_tolerance=field.state_tolerance,
    pressure_tolerance=field.pressure_tolerance,
  )


def _translate_euler_ambient_shock_field(
  field: MocEulerAmbientShockFieldResult,
  offset_x_m: float,
) -> MocEulerAmbientShockFieldResult:
  """Translate a converged exact open field for the deterministic mock.

  This fixture preserves the exact field's retained state and pressure data
  while rebuilding its companion strip on a fresh translated domain.  It is
  a planner exercise only: the translated result is not a replacement for a
  reflected/free-boundary solve.
  """

  if not isinstance(field, MocEulerAmbientShockFieldResult):
    raise TypeError('field must be a MocEulerAmbientShockFieldResult')
  if not field.converged:
    raise ValueError('field must be converged before the mock can translate it')
  if (
    field.shock_boundary is None
    or field.field is None
    or (
      field.ambient_march is None
      and field.ambient_companion_boundary is None
    )
  ):
    raise ValueError(
      'converged exact ambient shock field must retain shock, one ambient '
      'boundary source, and companion results'
    )
  offset = float(offset_x_m)
  if not isfinite(offset) or offset <= 0.0:
    raise ValueError('offset_x_m must be finite and positive')

  def translated_state(state: CharacteristicState) -> CharacteristicState:
    return replace(state, x_m=state.x_m + offset)

  def translated_point(
    point: tuple[float, float] | None,
  ) -> tuple[float, float] | None:
    if point is None:
      return None
    return point[0] + offset, point[1]

  shock = field.shock_boundary
  translated_shock = replace(
    shock,
    upstream_states=tuple(
      translated_state(state) for state in shock.upstream_states
    ),
    downstream_states=tuple(
      translated_state(state) for state in shock.downstream_states
    ),
    shock_points_m=tuple(
      (point[0] + offset, point[1]) for point in shock.shock_points_m
    ),
  )

  translated_march = None
  if field.ambient_march is not None:
    march = field.ambient_march
    translated_samples = tuple(
      replace(
        sample,
        point_m=(sample.point_m[0] + offset, sample.point_m[1]),
        state=translated_state(sample.state),
      )
      for sample in march.boundary_samples
    )
    translated_point_results = tuple(
      replace(
        point_result,
        state=(
          None
          if point_result.state is None
          else translated_state(point_result.state)
        ),
        point_m=translated_point(point_result.point_m),
      )
      for point_result in march.point_results
    )
    translated_ambient_boundary = replace(
      march.ambient_boundary,
      points_m=tuple(
        (point[0] + offset, point[1])
        for point in march.ambient_boundary.points_m
      ),
      states=tuple(
        translated_state(state) for state in march.ambient_boundary.states
      ),
    )
    translated_march = replace(
      march,
      shock_boundary=translated_shock,
      boundary_samples=translated_samples,
      point_results=translated_point_results,
      ambient_boundary=translated_ambient_boundary,
    )
  translated_companion_boundary = None
  if field.ambient_companion_boundary is not None:
    companion = field.ambient_companion_boundary
    translated_companion_boundary = replace(
      companion,
      shock_boundary=translated_shock,
      samples=tuple(
        replace(
          sample,
          state=translated_state(sample.state),
        )
        for sample in companion.samples
      ),
    )
  translated_wedge = None
  if field.attachment_wedge is not None:
    translated_wedge = replace(
      field.attachment_wedge,
      trials=tuple(
        replace(
          trial,
          point_result=replace(
            trial.point_result,
            state=(
              None
              if trial.point_result.state is None
              else translated_state(trial.point_result.state)
            ),
            point_m=translated_point(trial.point_result.point_m),
          ),
        )
        for trial in field.attachment_wedge.trials
      ),
      accepted_point_m=translated_point(
        field.attachment_wedge.accepted_point_m
      ),
      accepted_state=(
        None
        if field.attachment_wedge.accepted_state is None
        else translated_state(field.attachment_wedge.accepted_state)
      ),
    )
  translated_companion = _translate_euler_companion_field(
    field.field,
    offset,
  )
  return replace(
    field,
    shock_boundary=translated_shock,
    ambient_march=translated_march,
    ambient_companion_boundary=translated_companion_boundary,
    attachment_wedge=translated_wedge,
    field=translated_companion,
  )


def _characteristic_strip_fingerprint(
  strip: MocSourceCharacteristicStripResult | None,
) -> str | None:
  """Return a deterministic identity for a consumed source-strip domain."""

  if strip is None:
    return None

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = '\n'.join((
    f'total-pressure:{strip.total_pressure_Pa.hex()}',
    f'window-start:{strip.source_window_start_index}',
    f'window-total:{strip.source_window_total_count}',
    'plus:' + '\n'.join(
      state_payload(state) for state in strip.plus_source_states
    ),
    'minus:' + '\n'.join(
      state_payload(state) for state in strip.minus_source_states
    ),
  ))
  return sha256(payload.encode('ascii')).hexdigest()


def _alternating_source_band_fingerprint(
  source_band: MocReflectedDomainAlternatingSourceResult,
) -> str:
  """Return a deterministic identity for a consumed alternating source band.

  The incoming handoff is intentionally excluded.  A caller cannot make a
  reused source domain fresh merely by attaching it to a different prior
  cell; the geometric/state-bearing source rows must be independently solved.
  """

  def state_payload(state: CharacteristicState) -> str:
    return '|'.join(
      value.hex()
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )

  payload = '\n'.join((
    'centerline:' + '\n'.join(
      state_payload(state)
      for state in source_band.centerline_source_states
    ),
    'outer:' + '\n'.join(
      state_payload(state)
      for state in source_band.outer_source_states
    ),
    'centerline-pressure:' + '|'.join(
      value.hex() for value in source_band.centerline_total_pressure_Pa
    ),
    'outer-pressure:' + '|'.join(
      value.hex() for value in source_band.outer_total_pressure_Pa
    ),
  ))
  return sha256(payload.encode('ascii')).hexdigest()


def _source_strip_fingerprint(
  continuation: MocSourceStripContinuationResult,
) -> str | None:
  """Return a deterministic identity for a continuation's source strip."""

  return _characteristic_strip_fingerprint(continuation.strip)


def _caustic_upstream_remesh_fingerprint(
  remesh: MocCausticUpstreamRemeshResult,
) -> str | None:
  """Return a deterministic identity for a consumed caustic remesh."""

  request = remesh.request
  strip_fingerprint = _characteristic_strip_fingerprint(remesh.strip)
  if request is None or strip_fingerprint is None:
    return None
  event = request.event_point_m
  payload = '|'.join((
    'event:' + '|'.join(value.hex() for value in event),
    f'upstream-edge:{request.upstream_edge_index}',
    f'total-pressure:{request.total_pressure_Pa.hex()}',
    f'strip:{strip_fingerprint}',
  ))
  return sha256(payload.encode('ascii')).hexdigest()


def _result_handoff_fields(
  boundary: tuple[MocChainBoundarySample, ...],
  boundary_kind: MocChainBoundaryKind | None,
) -> dict[str, Any]:
  """Return the outgoing handoff audit fields for a returned cell/field."""

  pressure_range = None
  if boundary:
    pressures = tuple(sample.total_pressure_Pa for sample in boundary)
    pressure_range = (min(pressures), max(pressures))
  return {
    'result_boundary_kind': boundary_kind if boundary else None,
    'result_handoff_sample_count': len(boundary),
    'result_total_pressure_range_Pa': pressure_range,
    'result_handoff_fingerprint': _handoff_fingerprint(boundary),
  }


def _field_incoming_handoff(
  field: MocPostShockCharacteristicFieldResult | MocPhysicalPostShockFieldResult,
) -> tuple[MocChainBoundarySample, ...] | None:
  """Extract the exact input handoff retained by a returned solver field."""

  states = getattr(field, 'incoming_handoff_states', None)
  pressures = getattr(field, 'incoming_handoff_total_pressure_Pa', None)
  if states is None or pressures is None:
    return None
  try:
    if len(states) != len(pressures):
      return None
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(states, pressures, strict=True)
    )
  except (TypeError, ValueError):
    return None


def _result_consumed_handoff_fields(
  boundary: tuple[MocChainBoundarySample, ...] | None,
) -> dict[str, Any]:
  """Return provenance fields for the handoff actually consumed by a field."""

  if boundary is None:
    return {
      'result_consumed_handoff_sample_count': None,
      'result_consumed_total_pressure_range_Pa': None,
      'result_consumed_handoff_fingerprint': None,
    }
  pressure_range = None
  if boundary:
    pressures = tuple(sample.total_pressure_Pa for sample in boundary)
    pressure_range = (min(pressures), max(pressures))
  return {
    'result_consumed_handoff_sample_count': len(boundary),
    'result_consumed_total_pressure_range_Pa': pressure_range,
    'result_consumed_handoff_fingerprint': _handoff_fingerprint(boundary),
  }


def _with_chain_solver_context(
  decision: MocChainTerminationDecision,
  *,
  model: str,
  next_cell_index: int,
  incoming_handoff: tuple[MocChainBoundarySample, ...],
) -> MocChainTerminationDecision:
  """Retain planner context when a nested solver returns a typed stop.

  Source/remesh adapters are allowed to return their own termination decision,
  but that decision still belongs to a specific continued-cell attempt.  The
  outer planner must not discard that identity when it forwards the decision
  to the chain contract.
  """

  diagnostics = dict(decision.diagnostics)
  diagnostics.update({
    'continuation_model': model,
    'next_cell_index': next_cell_index,
    'incoming_handoff_sample_count': len(incoming_handoff),
    'incoming_handoff_fingerprint': _handoff_fingerprint(incoming_handoff),
  })
  return replace(decision, diagnostics=diagnostics)


def _audit_mixed_regime_entropy_handoff(
  request: MocMixedRegimePerimeterRequest,
) -> tuple[
  MocMixedRegimeEntropyHandoffResult | None,
  dict[str, Any] | None,
  bool,
  str | None,
]:
  """Build and independently measure one terminal entropy handoff.

  The planner records this seam next to a terminal result so downstream work
  can consume the exact pressure-loss profile.  The helper intentionally
  returns an acceptance flag separate from the handoff's own convenience
  properties: a planner gate must include the independent measurement and
  preserve the non-promotable terminal boundary.
  """

  try:
    handoff = request.entropy_handoff()
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return None, None, False, f'could not build entropy handoff: {error}'
  try:
    # Keep validation imports local: validation imports the planner module.
    from exhaust_plume.validation.moc_measurements import (
      measure_mixed_regime_entropy_handoff,
    )

    measurement = measure_mixed_regime_entropy_handoff(request, handoff)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return handoff, None, False, f'could not measure entropy handoff: {error}'
  accepted = bool(
    handoff.converged
    and handoff.entropy_transport_verified
    and handoff.chain_promotion_blocked
    and not handoff.physical_closure_verified
    and not handoff.production_claim_allowed
    and measurement.converged
    and measurement.handoff_verified
    and measurement.chain_promotion_blocked
    and not measurement.physical_closure_verified
    and not measurement.production_claim_allowed
  )
  return handoff, measurement.as_report(), accepted, None


def _audit_mixed_regime_entropy_transport(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  field: MocMixedRegimeFieldResult,
  source_arc_length_m: Sequence[float],
  streamline_ids: Sequence[int],
) -> tuple[
  MocMixedRegimeEntropyTransportResult | None,
  dict[str, Any] | None,
  bool,
  str | None,
]:
  """Solve and independently measure one explicit entropy field seam."""

  try:
    transport = solve_mixed_regime_entropy_transport_boundary(
      request,
      handoff,
      field,
      source_arc_length_m,
      streamline_ids,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return None, None, False, f'could not solve entropy transport boundary: {error}'
  try:
    # Keep validation imports local: validation imports the planner module.
    from exhaust_plume.validation.moc_measurements import (
      measure_mixed_regime_entropy_transport_boundary,
    )

    measurement = measure_mixed_regime_entropy_transport_boundary(
      request,
      handoff,
      field,
      transport,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return transport, None, False, f'could not measure entropy transport boundary: {error}'
  accepted = bool(
    transport.converged
    and transport.entropy_transport_verified
    and transport.chain_promotion_blocked
    and not transport.physical_closure_verified
    and not transport.canonical_free_boundary_verified
    and not transport.production_claim_allowed
    and measurement.converged
    and measurement.transport_verified
    and measurement.chain_promotion_blocked
    and not measurement.physical_closure_verified
    and not measurement.production_claim_allowed
  )
  return transport, measurement.as_report(), accepted, None


@dataclass(frozen=True, slots=True)
class MocChainPlannerResult:
  """A chain result plus planner provenance and callback audit steps."""

  chain: MocChainResult
  planner_kind: MocChainPlannerKind
  steps: tuple[MocChainPlannerStep, ...] = ()
  claim_status: str = ''
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.chain, MocChainResult):
      raise TypeError('chain must be a MocChainResult')
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    steps = tuple(self.steps)
    if any(not isinstance(step, MocChainPlannerStep) for step in steps):
      raise TypeError('steps must contain MocChainPlannerStep values')
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def resolved(self) -> bool:
    return self.chain.resolved
  ####

  @property
  def physical_termination(self) -> bool:
    return self.chain.physical_termination
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """Whether this planner provenance may be called production evidence."""

    return False
  ####

  @property
  def handoff_links_verified(self) -> bool | None:
    """Whether every continued callback consumed the prior result handoff."""

    if len(self.steps) < 2:
      return None
    return all(step.incoming_handoff_link_verified is True for step in self.steps[1:])

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'step_count': len(self.steps),
      'handoff_links_verified': self.handoff_links_verified,
      'steps': [step.as_report() for step in self.steps],
      'chain': self.chain.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldPlannerResult:
  """Planner boundary for a locally audited Euler companion field.

  The Euler companion strip is a useful higher-fidelity field handoff, but it
  is not a resolved shock cell: its companion/ambient boundary remains an
  explicit closure input.  This wrapper keeps that distinction at the
  planner boundary and exposes the field's typed non-physical stop without
  manufacturing a ``MocChainCell``.
  """

  field: MocEulerCompanionFieldResult
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocEulerCompanionFieldResult):
      raise TypeError(
        'field must be a MocEulerCompanionFieldResult'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    expected = self.field.as_chain_termination_decision()
    if self.termination != expected:
      raise ValueError(
        'termination must match field.as_chain_termination_decision()'
      )
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'Euler companion field planning must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def resolved(self) -> bool:
    """Whether the local companion strip assembled numerically."""

    return self.field.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The companion strip does not solve the global physical closure."""

    return False
  ####

  @property
  def physical_termination(self) -> bool:
    """Whether the field supplied a verified physical chain endpoint."""

    return self.termination.physical_termination
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Prevent an open companion field from becoming a chain cell."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """Planner/reference results never support a product claim."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': self.termination.as_report(),
      'field': self.field.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldContinuationSolve:
  """One open Euler-field continuation result and its consumed frontier.

  The frontier is retained beside the new field because the Euler companion
  strip does not yet have the physical perimeter required by
  ``MocChainCell``.  A future reflected-field solver can replace this
  research wrapper without changing the exact-handoff contract.
  """

  field: MocEulerCompanionFieldResult
  incoming_handoff: tuple[MocChainBoundarySample, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocEulerCompanionFieldResult):
      raise TypeError(
        'field must be a MocEulerCompanionFieldResult'
      )
    handoff = tuple(self.incoming_handoff)
    if not handoff:
      raise ValueError('incoming_handoff must contain state-carrying samples')
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', handoff)
  ####

  @property
  def outgoing_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the new open field's bounded downstream frontier."""

    return self.field.downstream_handoff
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'field_status': self.field.status.value,
      'field_converged': self.field.converged,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(
        self.incoming_handoff
      ),
      'outgoing_handoff_sample_count': len(self.outgoing_handoff),
      'outgoing_handoff_fingerprint': _handoff_fingerprint(
        self.outgoing_handoff
      ),
      'field_fingerprint': _euler_companion_field_fingerprint(self.field),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainStep:
  """One callback attempt in an open Euler-field continuation sequence."""

  next_field_index: int
  incoming_handoff_sample_count: int
  incoming_handoff_fingerprint: str | None
  incoming_handoff_link_verified: bool
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_field_status: str | None = None
  result_field_fingerprint: str | None = None
  result_handoff_sample_count: int | None = None
  result_handoff_fingerprint: str | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.next_field_index, bool)
      or not isinstance(self.next_field_index, int)
      or self.next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    if (
      isinstance(self.incoming_handoff_sample_count, bool)
      or not isinstance(self.incoming_handoff_sample_count, int)
      or self.incoming_handoff_sample_count < 0
    ):
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    if not isinstance(self.incoming_handoff_link_verified, bool):
      raise TypeError('incoming_handoff_link_verified must be a bool')
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    for name in (
      'incoming_handoff_fingerprint',
      'result_status',
      'result_field_status',
      'result_field_fingerprint',
      'result_handoff_fingerprint',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if self.result_handoff_sample_count is not None:
      if (
        isinstance(self.result_handoff_sample_count, bool)
        or not isinstance(self.result_handoff_sample_count, int)
        or self.result_handoff_sample_count < 0
      ):
        raise ValueError('result_handoff_sample_count must be nonnegative')
    if self.result_termination_reason is not None and not isinstance(
      self.result_termination_reason,
      MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
      self.result_physical_termination,
      bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'next_field_index': self.next_field_index,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_field_status': self.result_field_status,
      'result_field_fingerprint': self.result_field_fingerprint,
      'result_handoff_sample_count': self.result_handoff_sample_count,
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainPlannerResult:
  """A research-only sequence of open Euler companion fields.

  This is intentionally not a ``MocChainResult``.  Each field has a bounded
  characteristic frontier, but the reflected/free-boundary and entropy
  closure needed to make a physical shock cell remains unsolved.  The result
  exists to exercise repeated exact state/pressure handoffs without allowing
  an open field to become a chain cell.
  """

  seed: MocEulerCompanionFieldResult
  fields: tuple[MocEulerCompanionFieldResult, ...]
  steps: tuple[MocEulerCompanionFieldChainStep, ...]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerCompanionFieldResult):
      raise TypeError('seed must be a MocEulerCompanionFieldResult')
    fields = tuple(self.fields)
    if not fields:
      raise ValueError('fields must retain the seed field')
    if fields[0] is not self.seed:
      raise ValueError('fields must retain seed as their first entry')
    if any(
      not isinstance(field, MocEulerCompanionFieldResult)
      for field in fields
    ):
      raise TypeError(
        'fields must contain MocEulerCompanionFieldResult values'
      )
    steps = tuple(self.steps)
    if any(
      not isinstance(step, MocEulerCompanionFieldChainStep)
      for step in steps
    ):
      raise TypeError(
        'steps must contain MocEulerCompanionFieldChainStep values'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'Euler companion field chains must use the upstream-coupled research '
        'planner kind'
      )
    object.__setattr__(self, 'fields', fields)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def field_count(self) -> int:
    return len(self.fields)
  ####

  @property
  def continued_field_count(self) -> int:
    return max(0, len(self.fields) - 1)
  ####

  @property
  def resolved(self) -> bool:
    """Whether the configured local field sequence reached its mock stop."""

    return bool(
      self.fields
      and all(field.converged for field in self.fields)
      and self.termination.reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    )
  ####

  @property
  def handoff_links_verified(self) -> bool | None:
    if not self.steps:
      return None
    return all(step.incoming_handoff_link_verified for step in self.steps)
  ####

  @property
  def physical_closure_verified(self) -> bool:
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
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'handoff_links_verified': self.handoff_links_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fields': [field.as_report() for field in self.fields],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldChainMock:
  """Deterministic multi-strip fixture for the open Euler planner seam.

  Each accepted strip is rebuilt by translating the previous strip in ``x``
  and re-running the Euler companion-field assembler.  This exercises fresh
  domains and repeated frontier bookkeeping, but it does not claim that the
  translated strip consumed a solved reflected shock or entropy field.  The
  fixture therefore remains below ``MocChainCell`` promotion.
  """

  total_field_count: int = 3
  axial_translation_m: float = 2.0
  model: str = 'translated-euler-companion-field-chain-mock'

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_field_count, bool)
      or not isinstance(self.total_field_count, int)
      or self.total_field_count < 1
    ):
      raise ValueError('total_field_count must be a positive integer')
    if not isfinite(float(self.axial_translation_m)) or self.axial_translation_m <= 0.0:
      raise ValueError('axial_translation_m must be finite and positive')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'axial_translation_m', float(self.axial_translation_m))
    object.__setattr__(self, 'model', model)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'total_field_count_including_seed': self.total_field_count,
      'axial_translation_m': self.axial_translation_m,
      'fresh_domain_policy': 'translated-x-domain-reassembled-by-euler-strip-solver',
      'incoming_handoff_policy': (
        'exact-open-downstream-frontier-recorded-but-not-reinterpreted-as-a-'
        'physical-shock-upstream-state'
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'deterministic-open-euler-field-sequence-mock; '
        'reflected-free-boundary-and-entropy-closure-pending'
      ),
    }
  ####

  def solve_next(
    self,
    current: MocEulerCompanionFieldResult,
    next_field_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocEulerCompanionFieldContinuationSolve | MocChainTerminationDecision:
    """Return one fresh translated strip or the configured mock stop."""

    if not isinstance(current, MocEulerCompanionFieldResult):
      raise TypeError('current must be a MocEulerCompanionFieldResult')
    if (
      isinstance(next_field_index, bool)
      or not isinstance(next_field_index, int)
      or next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    handoff = tuple(incoming_handoff)
    if handoff != current.downstream_handoff:
      raise ValueError(
        'incoming_handoff must exactly match current.downstream_handoff'
      )
    if next_field_index > self.total_field_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'Euler companion field chain mock exhausted its configured '
          f'{self.total_field_count}-field sequence'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_field_index': next_field_index,
          'incoming_handoff_sample_count': len(handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
        },
      )
    translated = _translate_euler_companion_field(
      current,
      self.axial_translation_m,
    )
    return MocEulerCompanionFieldContinuationSolve(
      field=translated,
      incoming_handoff=handoff,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldPlannerResult:
  """Planner boundary for an exact ambient-coupled Euler field.

  The ambient-coupled result can retain a shock, an independently checked
  pressure boundary, and an open characteristic strip.  It still does not
  own the reflected/free-boundary perimeter required by ``MocChainCell``.
  This wrapper makes that stop available to planning code without relabeling
  the field as a physical shock cell.
  """

  field: MocEulerAmbientShockFieldResult
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocEulerAmbientShockFieldResult):
      raise TypeError(
        'field must be a MocEulerAmbientShockFieldResult'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    expected = self.field.as_chain_termination_decision()
    if self.termination != expected:
      raise ValueError(
        'termination must match field.as_chain_termination_decision()'
      )
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'Euler ambient shock field planning must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def resolved(self) -> bool:
    """Whether the exact ambient-coupled field assembled locally."""

    return self.field.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def physical_termination(self) -> bool:
    return self.termination.physical_termination
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
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': self.termination.as_report(),
      'field': self.field.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldContinuationSolve:
  """One open exact ambient-field continuation and its consumed frontier."""

  field: MocEulerAmbientShockFieldResult
  incoming_handoff: tuple[MocChainBoundarySample, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocEulerAmbientShockFieldResult):
      raise TypeError(
        'field must be a MocEulerAmbientShockFieldResult'
      )
    handoff = tuple(self.incoming_handoff)
    if not handoff:
      raise ValueError('incoming_handoff must contain state-carrying samples')
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', handoff)
  ####

  @property
  def outgoing_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    return self.field.downstream_handoff
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'field_status': self.field.status.value,
      'field_converged': self.field.converged,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(
        self.incoming_handoff
      ),
      'outgoing_handoff_sample_count': len(self.outgoing_handoff),
      'outgoing_handoff_fingerprint': _handoff_fingerprint(
        self.outgoing_handoff
      ),
      'field_fingerprint': _euler_ambient_shock_field_fingerprint(self.field),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldChainStep:
  """One callback attempt in an exact open ambient-field sequence."""

  next_field_index: int
  incoming_handoff_sample_count: int
  incoming_handoff_fingerprint: str | None
  incoming_handoff_link_verified: bool
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_field_status: str | None = None
  result_field_fingerprint: str | None = None
  result_handoff_sample_count: int | None = None
  result_handoff_fingerprint: str | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.next_field_index, bool)
      or not isinstance(self.next_field_index, int)
      or self.next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    if (
      isinstance(self.incoming_handoff_sample_count, bool)
      or not isinstance(self.incoming_handoff_sample_count, int)
      or self.incoming_handoff_sample_count < 0
    ):
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    if not isinstance(self.incoming_handoff_link_verified, bool):
      raise TypeError('incoming_handoff_link_verified must be a bool')
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    for name in (
      'incoming_handoff_fingerprint',
      'result_status',
      'result_field_status',
      'result_field_fingerprint',
      'result_handoff_fingerprint',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if self.result_handoff_sample_count is not None:
      if (
        isinstance(self.result_handoff_sample_count, bool)
        or not isinstance(self.result_handoff_sample_count, int)
        or self.result_handoff_sample_count < 0
      ):
        raise ValueError('result_handoff_sample_count must be nonnegative')
    if self.result_termination_reason is not None and not isinstance(
      self.result_termination_reason,
      MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
      self.result_physical_termination,
      bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'next_field_index': self.next_field_index,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_field_status': self.result_field_status,
      'result_field_fingerprint': self.result_field_fingerprint,
      'result_handoff_sample_count': self.result_handoff_sample_count,
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldChainPlannerResult:
  """A research-only sequence of exact open ambient shock fields."""

  seed: MocEulerAmbientShockFieldResult
  fields: tuple[MocEulerAmbientShockFieldResult, ...]
  steps: tuple[MocEulerAmbientShockFieldChainStep, ...]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerAmbientShockFieldResult):
      raise TypeError('seed must be a MocEulerAmbientShockFieldResult')
    fields = tuple(self.fields)
    if not fields:
      raise ValueError('fields must retain the seed field')
    if fields[0] is not self.seed:
      raise ValueError('fields must retain seed as their first entry')
    if any(
      not isinstance(field, MocEulerAmbientShockFieldResult)
      for field in fields
    ):
      raise TypeError(
        'fields must contain MocEulerAmbientShockFieldResult values'
      )
    steps = tuple(self.steps)
    if any(
      not isinstance(step, MocEulerAmbientShockFieldChainStep)
      for step in steps
    ):
      raise TypeError(
        'steps must contain MocEulerAmbientShockFieldChainStep values'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'Euler ambient shock field chains must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'fields', fields)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def field_count(self) -> int:
    return len(self.fields)
  ####

  @property
  def continued_field_count(self) -> int:
    return max(0, len(self.fields) - 1)
  ####

  @property
  def resolved(self) -> bool:
    return bool(
      self.fields
      and all(field.converged for field in self.fields)
      and self.termination.reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    )
  ####

  @property
  def handoff_links_verified(self) -> bool | None:
    if not self.steps:
      return None
    return all(step.incoming_handoff_link_verified for step in self.steps)
  ####

  @property
  def physical_closure_verified(self) -> bool:
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
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'handoff_links_verified': self.handoff_links_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fields': [field.as_report() for field in self.fields],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientShockFieldChainMock:
  """Deterministic translated exact-open-field sequence fixture.

  A converged exact ambient field is translated and its companion strip is
  rebuilt on each fresh domain.  A failed seed or field remains a typed stop;
  the mock never turns an attachment or entropy failure into a chain cell.
  """

  total_field_count: int = 3
  axial_translation_m: float = 2.0
  model: str = 'translated-euler-ambient-shock-field-chain-mock'

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_field_count, bool)
      or not isinstance(self.total_field_count, int)
      or self.total_field_count < 1
    ):
      raise ValueError('total_field_count must be a positive integer')
    if not isfinite(float(self.axial_translation_m)) or self.axial_translation_m <= 0.0:
      raise ValueError('axial_translation_m must be finite and positive')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'axial_translation_m', float(self.axial_translation_m))
    object.__setattr__(self, 'model', model)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'total_field_count_including_seed': self.total_field_count,
      'axial_translation_m': self.axial_translation_m,
      'fresh_domain_policy': (
        'translated-x-domain-reassembled-by-exact-ambient-shock-field-mock'
      ),
      'incoming_handoff_policy': (
        'exact-open-downstream-frontier-recorded-but-not-reinterpreted-as-a-'
        'physical-shock-upstream-state'
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'deterministic-open-euler-ambient-shock-field-sequence-mock; '
        'reflected-free-boundary-and-entropy-closure-pending'
      ),
    }
  ####

  def solve_next(
    self,
    current: MocEulerAmbientShockFieldResult,
    next_field_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> (
    MocEulerAmbientShockFieldContinuationSolve
    | MocChainTerminationDecision
  ):
    """Return one fresh translated exact field or a typed mock stop."""

    if not isinstance(current, MocEulerAmbientShockFieldResult):
      raise TypeError('current must be a MocEulerAmbientShockFieldResult')
    if (
      isinstance(next_field_index, bool)
      or not isinstance(next_field_index, int)
      or next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    handoff = tuple(incoming_handoff)
    if handoff != current.downstream_handoff:
      raise ValueError(
        'incoming_handoff must exactly match current.downstream_handoff'
      )
    if next_field_index > self.total_field_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'Euler ambient shock field chain mock exhausted its configured '
          f'{self.total_field_count}-field sequence'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_field_index': next_field_index,
          'incoming_handoff_sample_count': len(handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
        },
      )
    if not current.converged:
      return current.as_chain_termination_decision()
    translated = _translate_euler_ambient_shock_field(
      current,
      self.axial_translation_m,
    )
    return MocEulerAmbientShockFieldContinuationSolve(
      field=translated,
      incoming_handoff=handoff,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedMixedRegimeClosureMock:
  """Explicit synthetic terminal closure fixture for planner validation.

  The fixture supplies a small rectangular perimeter and a constant scalar
  subsonic state, then routes both through the real mixed-regime perimeter
  adapter.  It exists to exercise the exact terminal seam and typed closure
  result while the canonical downstream perimeter is still unsolved.  The
  pressure-outflow condition is intentionally the only supported condition:
  this mock must not be mistaken for a free-boundary or slip-wall solver.
  """

  streamwise_length_m: float = 0.02
  transverse_length_m: float = 0.01
  radial_divisions: int = 2
  condition_kind: MocMixedRegimeDownstreamConditionKind = (
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION
  )
  model: str = 'prescribed-pressure-outflow-mixed-regime-closure-mock'

  def __post_init__(self) -> None:
    for name, value in (
      ('streamwise_length_m', self.streamwise_length_m),
      ('transverse_length_m', self.transverse_length_m),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if (
      isinstance(self.radial_divisions, bool)
      or not isinstance(self.radial_divisions, int)
      or self.radial_divisions < 1
    ):
      raise ValueError('radial_divisions must be a positive integer')
    if not isinstance(
      self.condition_kind,
      MocMixedRegimeDownstreamConditionKind,
    ):
      raise TypeError(
        'condition_kind must be a MocMixedRegimeDownstreamConditionKind'
      )
    if self.condition_kind is not MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION:
      raise ValueError(
        'MocPrescribedMixedRegimeClosureMock only supports the '
        'PRESSURE_OUTFLOW_SECTION condition'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'streamwise_length_m', float(self.streamwise_length_m))
    object.__setattr__(self, 'transverse_length_m', float(self.transverse_length_m))
    object.__setattr__(self, 'model', model)

  @property
  def production_claim_allowed(self) -> bool:
    """Whether this synthetic fixture may support a product claim."""

    return False

  def as_report(self) -> dict[str, Any]:
    """Return the fixture configuration and its hard fidelity ceiling."""

    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'streamwise_length_m': self.streamwise_length_m,
      'transverse_length_m': self.transverse_length_m,
      'radial_divisions': self.radial_divisions,
      'condition_kind': self.condition_kind.value,
      'claim_status': (
        'prescribed-mixed-regime-pressure-outflow-closure-mock; '
        'canonical-downstream-perimeter-and-free-boundary-solve-pending'
      ),
    }

  @staticmethod
  def _validate_request(request: MocMixedRegimePerimeterRequest) -> None:
    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest'
      )

  def perimeter_points(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> tuple[tuple[float, float], ...]:
    """Return the explicit closed rectangle anchored at the terminal seam."""

    self._validate_request(request)
    x_m, y_m = request.terminal_point_m
    return (
      (x_m, y_m),
      (x_m + self.streamwise_length_m, y_m),
      (x_m + self.streamwise_length_m, y_m + self.transverse_length_m),
      (x_m, y_m + self.transverse_length_m),
      (x_m, y_m),
    )

  def specification(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeDownstreamPerimeterSpec:
    """Build the explicit pressure-outflow specification for one request."""

    self._validate_request(request)
    return MocMixedRegimeDownstreamPerimeterSpec(
      perimeter_points_m=self.perimeter_points(request),
      condition_kind=self.condition_kind,
      ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
      model=self.model,
    )

  def sample_at(
    self,
    request: MocMixedRegimePerimeterRequest,
    index: int,
    point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    """Return the constant scalar state at one exact prescribed point."""

    self._validate_request(request)
    points = self.perimeter_points(request)
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(points):
      raise ValueError('sample index is outside the prescribed perimeter')
    expected_point = points[index]
    try:
      received_point = (float(point[0]), float(point[1]))
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError('sample point must contain two numeric coordinates') from error
    if any(
      abs(received - expected) > 1.0e-10
      for received, expected in zip(received_point, expected_point, strict=True)
    ):
      raise ValueError('sample point does not match the prescribed perimeter')
    upstream_state = request.terminal.upstream_state
    if upstream_state is None:
      raise ValueError('terminal request does not expose its upstream state')
    return MocMixedRegimeFieldSample(
      point_m=expected_point,
      mach=request.terminal_downstream_mach,
      flow_angle_rad=request.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=request.terminal_downstream_pressure_Pa,
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=upstream_state.gamma,
    )

  def solve(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeClosureResult:
    """Solve the explicit fixture through the real downstream adapter."""

    self._validate_request(request)
    specification = self.specification(request)
    return solve_mixed_regime_downstream_perimeter(
      request,
      specification,
      self.sample_at,
      radial_divisions=self.radial_divisions,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocSolverGeneratedMixedRegimeClosureReference:
  """Planner fixture for the solver-owned downstream free-boundary lane.

  Unlike :class:`MocPrescribedMixedRegimeClosureMock`, this reference does
  not prescribe a rectangle or a constant state.  It shoots an effective
  outlet height from the terminal subsonic total state and an explicit
  ambient-pressure target, then submits the generated perimeter through the
  real mixed-boundary and scalar-field gates.  The effective inlet height is
  intentionally an input because a terminal point has no area information.
  """

  effective_inlet_height_m: float = 0.01
  downstream_length_m: float = 0.05
  ambient_pressure_Pa: float | None = None
  ambient_pressure_ratio: float = 0.8
  free_boundary_sample_count: int = 7
  radial_divisions: int = 2
  terminal_regularization_fraction: float = 0.05
  maximum_iterations: int = 40
  model: str = 'solver-owned-quasi-1d-ambient-free-boundary-reference'

  def __post_init__(self) -> None:
    for name, value in (
      ('effective_inlet_height_m', self.effective_inlet_height_m),
      ('downstream_length_m', self.downstream_length_m),
      ('ambient_pressure_ratio', self.ambient_pressure_ratio),
      ('terminal_regularization_fraction', self.terminal_regularization_fraction),
    ):
      if not isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if self.ambient_pressure_ratio >= 1.0:
      raise ValueError('ambient_pressure_ratio must be less than one')
    if self.ambient_pressure_Pa is not None and (
      not isfinite(float(self.ambient_pressure_Pa))
      or self.ambient_pressure_Pa <= 0.0
    ):
      raise ValueError('ambient_pressure_Pa must be finite and positive when supplied')
    for name, value, minimum in (
      ('free_boundary_sample_count', self.free_boundary_sample_count, 3),
      ('radial_divisions', self.radial_divisions, 1),
      ('maximum_iterations', self.maximum_iterations, 1),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
    if not 0.0 < self.terminal_regularization_fraction < 1.0:
      raise ValueError(
        'terminal_regularization_fraction must lie strictly between zero and one'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'effective_inlet_height_m', float(self.effective_inlet_height_m))
    object.__setattr__(self, 'downstream_length_m', float(self.downstream_length_m))
    object.__setattr__(self, 'ambient_pressure_Pa', (
      None
      if self.ambient_pressure_Pa is None
      else float(self.ambient_pressure_Pa)
    ))
    object.__setattr__(self, 'ambient_pressure_ratio', float(self.ambient_pressure_ratio))
    object.__setattr__(self, 'terminal_regularization_fraction', float(self.terminal_regularization_fraction))
    object.__setattr__(self, 'model', model)

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def _ambient_pressure(self, request: MocMixedRegimePerimeterRequest) -> float:
    if self.ambient_pressure_Pa is not None:
      return self.ambient_pressure_Pa
    return self.ambient_pressure_ratio * request.terminal_downstream_pressure_Pa

  def solve(
    self,
    request: MocMixedRegimePerimeterRequest,
  ) -> MocMixedRegimeFreeBoundaryResult:
    """Run the solver-owned reference against one exact terminal seam."""

    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    return solve_mixed_regime_downstream_free_boundary(
      request,
      ambient_pressure_Pa=self._ambient_pressure(request),
      effective_inlet_height_m=self.effective_inlet_height_m,
      downstream_length_m=self.downstream_length_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      radial_divisions=self.radial_divisions,
      terminal_regularization_fraction=self.terminal_regularization_fraction,
      maximum_iterations=self.maximum_iterations,
    )

  def solve_from_control_section(
    self,
    request: MocMixedRegimePerimeterRequest,
    control_section: MocMixedRegimeControlSection,
  ) -> MocMixedRegimeFreeBoundaryResult:
    """Run the reference using an explicit solver-supplied control section."""

    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    if not isinstance(control_section, MocMixedRegimeControlSection):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection'
      )
    return solve_mixed_regime_downstream_free_boundary_from_control_section(
      request,
      control_section,
      ambient_pressure_Pa=self._ambient_pressure(request),
      downstream_length_m=self.downstream_length_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      radial_divisions=self.radial_divisions,
      terminal_regularization_fraction=self.terminal_regularization_fraction,
      maximum_iterations=self.maximum_iterations,
    )

  def solve_from_control_section_flux(
    self,
    request: MocMixedRegimePerimeterRequest,
    control_section: MocMixedRegimeControlSection,
  ) -> MocMixedRegimeFreeBoundaryResult:
    """Run the opt-in integrated-flux quasi-one-dimensional reference.

    This path preserves distributed section flux when the scalar section is
    not terminal-equivalent.  It remains a reference height reduction and
    does not claim the pending downstream two-dimensional free-boundary solve.
    """

    if not isinstance(request, MocMixedRegimePerimeterRequest):
      raise TypeError('request must be a MocMixedRegimePerimeterRequest')
    if not isinstance(control_section, MocMixedRegimeControlSection):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection'
      )
    return solve_mixed_regime_downstream_free_boundary_from_control_section(
      request,
      control_section,
      ambient_pressure_Pa=self._ambient_pressure(request),
      downstream_length_m=self.downstream_length_m,
      free_boundary_sample_count=self.free_boundary_sample_count,
      radial_divisions=self.radial_divisions,
      terminal_regularization_fraction=self.terminal_regularization_fraction,
      maximum_iterations=self.maximum_iterations,
      use_integrated_flux=True,
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'effective_inlet_height_m': self.effective_inlet_height_m,
      'downstream_length_m': self.downstream_length_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'ambient_pressure_ratio': self.ambient_pressure_ratio,
      'free_boundary_sample_count': self.free_boundary_sample_count,
      'radial_divisions': self.radial_divisions,
      'terminal_regularization_fraction': self.terminal_regularization_fraction,
      'maximum_iterations': self.maximum_iterations,
      'control_section_flux_mode': (
        'available-through-solve_from_control_section_flux; '
        'quasi-1d-reference-only'
      ),
      'claim_status': (
        'solver-owned-quasi-1d-free-boundary-reference; '
        'canonical-reflected-moc-and-external-validation-pending'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocFirstCellFreeBoundaryCorrectionPlannerResult:
  """Planner guard for a first-cell free-boundary correction.

  A corrected first-cell research result is not itself a chain cell.  This
  wrapper preserves its typed termination decision at the planner boundary so
  callers can record an explicit open/fidelity stop without manufacturing a
  continued-cell handoff.
  """

  correction: MocFirstCellFreeBoundaryCorrectionResult
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.correction,
      MocFirstCellFreeBoundaryCorrectionResult,
    ):
      raise TypeError(
        'correction must be a MocFirstCellFreeBoundaryCorrectionResult'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    if self.termination != self.correction.as_chain_termination_decision():
      raise ValueError(
        'termination must preserve the correction-owned chain decision'
      )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def resolved(self) -> bool:
    """Whether the bounded correction reached its local scalar gate."""

    return self.correction.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Expose only the correction's local physical closure result."""

    return self.correction.physical_closure_verified
  ####

  @property
  def physical_termination(self) -> bool:
    """Whether the correction supplied a physical chain stop."""

    return self.termination.physical_termination
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """A correction guard never creates a continued-cell seed."""

    return self.correction.chain_promotion_blocked
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """Planner guards remain research-only."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': self.termination.as_report(),
      'correction': self.correction.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocFirstCellTerminalClosurePlannerResult:
  """Planner/audit result for one first-cell terminal closure attempt.

  This result deliberately is not a ``MocChainPlannerResult``: a terminal
  mixed-regime region is a chain stop, not a supersonic cell that can seed the
  next shock.  The optional closure is retained beside the terminal result so
  reports can distinguish an open physical boundary from a prescribed fixture
  that passed the local scalar/reference gates.
  """

  terminal: MocFirstCellTerminalClosureResult
  mixed_regime_closure: MocMixedRegimeClosureResult | None
  termination: MocChainTerminationDecision | None
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})
  mixed_regime_planar_handoff: MocMixedRegimePlanarSolveResult | None = None
  mixed_regime_entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None
  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.terminal, MocFirstCellTerminalClosureResult):
      raise TypeError(
        'terminal must be a MocFirstCellTerminalClosureResult'
      )
    if self.mixed_regime_closure is not None and not isinstance(
      self.mixed_regime_closure,
      MocMixedRegimeClosureResult,
    ):
      raise TypeError(
        'mixed_regime_closure must be a MocMixedRegimeClosureResult or None'
      )
    if self.termination is not None and not isinstance(
      self.termination,
      MocChainTerminationDecision,
    ):
      raise TypeError(
        'termination must be a MocChainTerminationDecision or None'
      )
    if self.mixed_regime_planar_handoff is not None and not isinstance(
      self.mixed_regime_planar_handoff,
      MocMixedRegimePlanarSolveResult,
    ):
      raise TypeError(
        'mixed_regime_planar_handoff must be a '
        'MocMixedRegimePlanarSolveResult or None'
      )
    if self.mixed_regime_entropy_handoff is not None and not isinstance(
      self.mixed_regime_entropy_handoff,
      MocMixedRegimeEntropyHandoffResult,
    ):
      raise TypeError(
        'mixed_regime_entropy_handoff must be a '
        'MocMixedRegimeEntropyHandoffResult or None'
      )
    if self.mixed_regime_entropy_transport is not None:
      if not isinstance(
        self.mixed_regime_entropy_transport,
        MocMixedRegimeEntropyTransportResult,
      ):
        raise TypeError(
          'mixed_regime_entropy_transport must be a '
          'MocMixedRegimeEntropyTransportResult or None'
        )
      if self.mixed_regime_entropy_handoff is None:
        raise ValueError(
          'mixed_regime_entropy_transport requires an entropy handoff'
        )
      if self.mixed_regime_entropy_transport.handoff != (
        self.mixed_regime_entropy_handoff
      ) or self.mixed_regime_entropy_transport.request != (
        self.mixed_regime_entropy_handoff.request
      ):
        raise ValueError(
          'mixed_regime_entropy_transport must retain the exact entropy seam'
        )
      expected_field = (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.field
      )
      if expected_field is None and self.mixed_regime_closure is not None:
        expected_field = self.mixed_regime_closure.field
      if expected_field is not None and (
        self.mixed_regime_entropy_transport.field != expected_field
      ):
        raise ValueError(
          'mixed_regime_entropy_transport must retain the exact downstream field'
        )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def resolved(self) -> bool:
    """Whether the supersonic terminal region itself converged."""

    return self.terminal.converged

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the terminal and its attached mixed-regime field passed."""

    return self.terminal.physical_closure_verified

  @property
  def physical_termination(self) -> bool:
    """Whether the retained decision is a verified physical chain stop."""

    return bool(
      self.termination is not None
      and self.termination.physical_termination
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal mixed-regime result never becomes a supersonic next cell."""

    return self.terminal.chain_promotion_blocked

  @property
  def production_claim_allowed(self) -> bool:
    """Planner and prescribed-fixture results cannot support product claims."""

    return False

  @property
  def mixed_regime_entropy_handoff_verified(self) -> bool:
    """Whether the planner retained an independently audited entropy seam."""

    return bool(
      self.mixed_regime_entropy_handoff is not None
      and self.diagnostics.get('mixed_regime_entropy_handoff_verified') is True
    )

  @property
  def mixed_regime_entropy_transport_verified(self) -> bool:
    """Whether the explicit entropy-to-field seam passed its audit."""

    return bool(
      self.mixed_regime_entropy_transport is not None
      and self.diagnostics.get('mixed_regime_entropy_transport_verified') is True
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'mixed_regime_entropy_handoff_verified': (
        self.mixed_regime_entropy_handoff_verified
      ),
      'mixed_regime_entropy_transport_verified': (
        self.mixed_regime_entropy_transport_verified
      ),
      'termination': (
        None if self.termination is None else self.termination.as_report()
      ),
      'terminal': self.terminal.as_report(),
      'mixed_regime_closure': (
        None
        if self.mixed_regime_closure is None
        else self.mixed_regime_closure.as_report()
      ),
      'mixed_regime_planar_handoff': (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.as_report()
      ),
      'mixed_regime_entropy_handoff': (
        None
        if self.mixed_regime_entropy_handoff is None
        else self.mixed_regime_entropy_handoff.as_report()
      ),
      'mixed_regime_entropy_transport': (
        None
        if self.mixed_regime_entropy_transport is None
        else self.mixed_regime_entropy_transport.as_report()
      ),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocPhysicalPostShockTerminalPatchPlannerResult:
  """Planner result for a continued physical field reaching a terminal.

  ``chain_planner`` records the exact cell-to-terminal callback and typed
  physical stop.  ``transition`` retains the solver-owned terminal artifacts
  so the optional mixed-regime mock or reference can consume the exact shock
  seam afterward.  The downstream result is intentionally reported beside,
  never attached as, the supersonic chain cell.
  """

  chain_planner: MocChainPlannerResult
  transition: MocPhysicalPostShockTerminalPatchTransitionResult | None
  mixed_regime_closure: MocMixedRegimeClosureResult | None
  mixed_regime_reference: MocMixedRegimeFreeBoundaryResult | None
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})
  mixed_regime_planar_handoff: MocMixedRegimePlanarSolveResult | None = None
  mixed_regime_entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None
  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.chain_planner, MocChainPlannerResult):
      raise TypeError('chain_planner must be a MocChainPlannerResult')
    if self.transition is not None and not isinstance(
      self.transition,
      MocPhysicalPostShockTerminalPatchTransitionResult,
    ):
      raise TypeError(
        'transition must be a '
        'MocPhysicalPostShockTerminalPatchTransitionResult or None'
      )
    if self.mixed_regime_closure is not None and not isinstance(
      self.mixed_regime_closure,
      MocMixedRegimeClosureResult,
    ):
      raise TypeError(
        'mixed_regime_closure must be a MocMixedRegimeClosureResult or None'
      )
    if self.mixed_regime_reference is not None and not isinstance(
      self.mixed_regime_reference,
      MocMixedRegimeFreeBoundaryResult,
    ):
      raise TypeError(
        'mixed_regime_reference must be a '
        'MocMixedRegimeFreeBoundaryResult or None'
      )
    if self.mixed_regime_closure is not None and self.transition is not None:
      if self.transition.mixed_regime_request is None:
        raise ValueError(
          'mixed_regime_closure requires a transition mixed-regime seam'
        )
      if self.mixed_regime_closure.request != (
        self.transition.mixed_regime_request
      ):
        raise ValueError(
          'mixed_regime_closure must retain the exact transition seam'
        )
    if self.mixed_regime_reference is not None and self.transition is not None:
      if self.transition.mixed_regime_request is None:
        raise ValueError(
          'mixed_regime_reference requires a transition mixed-regime seam'
        )
      if self.mixed_regime_reference.request != (
        self.transition.mixed_regime_request
      ):
        raise ValueError(
          'mixed_regime_reference must retain the exact transition seam'
        )
    if self.mixed_regime_planar_handoff is not None:
      if not isinstance(
        self.mixed_regime_planar_handoff,
        MocMixedRegimePlanarSolveResult,
      ):
        raise TypeError(
          'mixed_regime_planar_handoff must be a '
          'MocMixedRegimePlanarSolveResult or None'
        )
      if self.transition is not None:
        if self.transition.mixed_regime_request is None:
          raise ValueError(
            'mixed_regime_planar_handoff requires a transition '
            'mixed-regime seam'
          )
        if self.mixed_regime_planar_handoff.request != (
          self.transition.mixed_regime_request
        ):
          raise ValueError(
            'mixed_regime_planar_handoff must retain the exact transition seam'
          )
    if self.mixed_regime_entropy_handoff is not None:
      if not isinstance(
        self.mixed_regime_entropy_handoff,
        MocMixedRegimeEntropyHandoffResult,
      ):
        raise TypeError(
          'mixed_regime_entropy_handoff must be a '
          'MocMixedRegimeEntropyHandoffResult or None'
        )
      if self.transition is None:
        raise ValueError(
          'mixed_regime_entropy_handoff requires a transition '
          'mixed-regime seam'
        )
      if self.transition.mixed_regime_request is None:
        raise ValueError(
          'mixed_regime_entropy_handoff requires a transition '
          'mixed-regime seam'
        )
      if self.mixed_regime_entropy_handoff.request != (
        self.transition.mixed_regime_request
      ):
        raise ValueError(
          'mixed_regime_entropy_handoff must retain the exact transition seam'
        )
    if self.mixed_regime_entropy_transport is not None:
      if not isinstance(
        self.mixed_regime_entropy_transport,
        MocMixedRegimeEntropyTransportResult,
      ):
        raise TypeError(
          'mixed_regime_entropy_transport must be a '
          'MocMixedRegimeEntropyTransportResult or None'
        )
      if self.mixed_regime_entropy_handoff is None:
        raise ValueError(
          'mixed_regime_entropy_transport requires an entropy handoff'
        )
      if self.mixed_regime_entropy_transport.handoff != (
        self.mixed_regime_entropy_handoff
      ) or self.mixed_regime_entropy_transport.request != (
        self.mixed_regime_entropy_handoff.request
      ):
        raise ValueError(
          'mixed_regime_entropy_transport must retain the exact entropy seam'
        )
      expected_field = (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.field
      )
      if expected_field is None and self.mixed_regime_closure is not None:
        expected_field = self.mixed_regime_closure.field
      if expected_field is not None and (
        self.mixed_regime_entropy_transport.field != expected_field
      ):
        raise ValueError(
          'mixed_regime_entropy_transport must retain the exact downstream field'
        )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def resolved(self) -> bool:
    """Whether the retained chain reached its typed terminal boundary."""

    return self.chain_planner.chain.resolved

  @property
  def physical_termination(self) -> bool:
    """Whether the downstream shock is a verified physical chain stop."""

    return self.chain_planner.chain.physical_termination

  @property
  def mixed_regime_model_closure_verified(self) -> bool:
    """Whether an optional local mock/reference field passed its own gates."""

    return bool(
      self.mixed_regime_closure is not None
      and self.mixed_regime_closure.converged
      and self.mixed_regime_closure.physical_closure_verified
    )

  @property
  def mixed_regime_planar_handoff_verified(self) -> bool:
    """Whether the adjacent planar downstream seam passed its local gates."""

    return bool(
      self.mixed_regime_planar_handoff is not None
      and self.mixed_regime_planar_handoff.handoff_verified
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the retained transition has an attached closed field.

    The planner's production claim remains false and chain promotion remains
    blocked even when a caller explicitly opts into attaching a field.  This
    property only reports the result-layer closure gates.
    """

    return bool(
      self.transition is not None
      and self.transition.physical_closure_verified
    )

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether the exact downstream field is retained on the transition."""

    return bool(
      self.transition is not None
      and self.transition.mixed_regime_field_complete
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal mixed-regime handoff cannot seed another supersonic cell."""

    return True

  @property
  def production_claim_allowed(self) -> bool:
    """Planner, mock, and scalar-reference results cannot support products."""

    return False

  @property
  def mixed_regime_entropy_handoff_verified(self) -> bool:
    """Whether the terminal entropy seam passed its independent audit."""

    return bool(
      self.mixed_regime_entropy_handoff is not None
      and self.diagnostics.get('mixed_regime_entropy_handoff_verified') is True
    )

  @property
  def mixed_regime_entropy_transport_verified(self) -> bool:
    """Whether the explicit entropy-to-field seam passed its audit."""

    return bool(
      self.mixed_regime_entropy_transport is not None
      and self.diagnostics.get('mixed_regime_entropy_transport_verified') is True
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_termination': self.physical_termination,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'mixed_regime_model_closure_verified': (
        self.mixed_regime_model_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'chain_planner': self.chain_planner.as_report(),
      'transition': (
        None if self.transition is None else self.transition.as_report()
      ),
      'mixed_regime_closure': (
        None
        if self.mixed_regime_closure is None
        else self.mixed_regime_closure.as_report()
      ),
      'mixed_regime_reference': (
        None
        if self.mixed_regime_reference is None
        else self.mixed_regime_reference.as_report()
      ),
      'mixed_regime_planar_handoff': (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.as_report()
      ),
      'mixed_regime_planar_handoff_verified': (
        self.mixed_regime_planar_handoff_verified
      ),
      'mixed_regime_entropy_handoff_verified': (
        self.mixed_regime_entropy_handoff_verified
      ),
      'mixed_regime_entropy_transport_verified': (
        self.mixed_regime_entropy_transport_verified
      ),
      'mixed_regime_entropy_handoff': (
        None
        if self.mixed_regime_entropy_handoff is None
        else self.mixed_regime_entropy_handoff.as_report()
      ),
      'mixed_regime_entropy_transport': (
        None
        if self.mixed_regime_entropy_transport is None
        else self.mixed_regime_entropy_transport.as_report()
      ),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocAmbientClosedPostShockChainTerminalPlannerResult:
  """Combined research result for a continued chain and terminal closure.

  ``chain_planner`` owns the accepted multi-cell supersonic prefix.  The
  optional ``terminal_planner`` runs once from that prefix's final field and
  owns the terminal shock/mixed-regime handoff.  The two results are kept
  separate because a mixed-regime field is a terminal closure, never another
  supersonic shock-cell seed.
  """

  chain_planner: MocChainPlannerResult
  terminal_planner: MocPhysicalPostShockTerminalPatchPlannerResult | None
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.chain_planner, MocChainPlannerResult):
      raise TypeError('chain_planner must be a MocChainPlannerResult')
    if self.terminal_planner is not None and not isinstance(
      self.terminal_planner,
      MocPhysicalPostShockTerminalPatchPlannerResult,
    ):
      raise TypeError(
        'terminal_planner must be a '
        'MocPhysicalPostShockTerminalPatchPlannerResult or None'
      )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    if self.planner_kind is not self.chain_planner.planner_kind:
      raise ValueError(
        'planner_kind must match the continued-chain planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )

  @property
  def cell_count(self) -> int:
    """Return the accepted supersonic prefix count."""

    return self.chain_planner.chain.cell_count

  @property
  def resolved(self) -> bool:
    """Whether the prefix and its terminal transition both resolved."""

    return bool(
      self.chain_planner.chain.resolved
      and self.terminal_planner is not None
      and self.terminal_planner.resolved
    )

  @property
  def physical_termination(self) -> bool:
    """Whether the terminal transition reached a verified physical stop."""

    return bool(
      self.terminal_planner is not None
      and self.terminal_planner.physical_termination
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Whether a mixed-regime field was explicitly attached and audited."""

    return bool(
      self.terminal_planner is not None
      and self.terminal_planner.physical_closure_verified
    )

  @property
  def mixed_regime_model_closure_verified(self) -> bool:
    """Whether the selected terminal mock/reference passed local gates."""

    return bool(
      self.terminal_planner is not None
      and self.terminal_planner.mixed_regime_model_closure_verified
    )

  @property
  def mixed_regime_planar_handoff(self) -> MocMixedRegimePlanarSolveResult | None:
    """Return the optional planar handoff beside the continued prefix."""

    return (
      None
      if self.terminal_planner is None
      else self.terminal_planner.mixed_regime_planar_handoff
    )

  @property
  def mixed_regime_planar_handoff_verified(self) -> bool:
    """Whether the optional planar handoff passed its local seam audit."""

    return bool(
      self.mixed_regime_planar_handoff is not None
      and self.mixed_regime_planar_handoff.handoff_verified
    )

  @property
  def mixed_regime_entropy_handoff(
    self,
  ) -> MocMixedRegimeEntropyHandoffResult | None:
    """Return the terminal entropy seam beside the continued prefix."""

    return (
      None
      if self.terminal_planner is None
      else self.terminal_planner.mixed_regime_entropy_handoff
    )

  @property
  def mixed_regime_entropy_handoff_verified(self) -> bool:
    """Whether the terminal entropy seam passed its independent audit."""

    return bool(
      self.terminal_planner is not None
      and self.terminal_planner.mixed_regime_entropy_handoff_verified
    )

  @property
  def mixed_regime_entropy_transport(
    self,
  ) -> MocMixedRegimeEntropyTransportResult | None:
    """Return the optional entropy-to-field seam beside the prefix."""

    return (
      None
      if self.terminal_planner is None
      else self.terminal_planner.mixed_regime_entropy_transport
    )

  @property
  def mixed_regime_entropy_transport_verified(self) -> bool:
    """Whether the terminal entropy-to-field seam passed its audit."""

    return bool(
      self.terminal_planner is not None
      and self.terminal_planner.mixed_regime_entropy_transport_verified
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal mixed-regime result cannot seed another shock cell."""

    return True

  @property
  def production_claim_allowed(self) -> bool:
    """Combined planner output is research evidence only."""

    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'physical_termination': self.physical_termination,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_model_closure_verified': (
        self.mixed_regime_model_closure_verified
      ),
      'mixed_regime_planar_handoff_verified': (
        self.mixed_regime_planar_handoff_verified
      ),
      'mixed_regime_planar_handoff': (
        None
        if self.mixed_regime_planar_handoff is None
        else self.mixed_regime_planar_handoff.as_report()
      ),
      'mixed_regime_entropy_handoff_verified': (
        self.mixed_regime_entropy_handoff_verified
      ),
      'mixed_regime_entropy_handoff': (
        None
        if self.mixed_regime_entropy_handoff is None
        else self.mixed_regime_entropy_handoff.as_report()
      ),
      'mixed_regime_entropy_transport_verified': (
        self.mixed_regime_entropy_transport_verified
      ),
      'mixed_regime_entropy_transport': (
        None
        if self.mixed_regime_entropy_transport is None
        else self.mixed_regime_entropy_transport.as_report()
      ),
      'cell_count': self.cell_count,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'chain_planner': self.chain_planner.as_report(),
      'terminal_planner': (
        None
        if self.terminal_planner is None
        else self.terminal_planner.as_report()
      ),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocCausticUpstreamContinuationPlannerResult:
  """Planner/audit result for a branch-explicit caustic continuation.

  A caustic continuation is an upstream research boundary, not a resolved
  shock-cell chain cell.  The planner therefore keeps the two-sided restart
  audit beside the optionally selected one-sided bridge and always retains a
  non-physical chain stop.  This makes a caller's branch choice observable
  without allowing the bounded bridge to raise its fidelity claim.
  """

  branch_audit: MocCausticUpstreamContinuationResult
  continuation: MocCausticUpstreamContinuationResult
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.branch_audit,
      MocCausticUpstreamContinuationResult,
    ):
      raise TypeError(
        'branch_audit must be a MocCausticUpstreamContinuationResult'
      )
    if not isinstance(
      self.continuation,
      MocCausticUpstreamContinuationResult,
    ):
      raise TypeError(
        'continuation must be a MocCausticUpstreamContinuationResult'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def branch_audit_verified(self) -> bool:
    """Whether both one-sided restart candidates passed their local gates."""

    return bool(
      self.branch_audit.status is (
        MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED
      )
      and len(self.branch_audit.restart_results) == 2
      and all(
        restart.converged
        and restart.caustic_handoff_verified
        and restart.family_band is not None
        and restart.family_band.converged
        for restart in self.branch_audit.restart_results
      )
    )

  @property
  def resolved(self) -> bool:
    """Whether the selected bounded continuation itself converged."""

    return self.continuation.converged

  @property
  def physical_closure_verified(self) -> bool:
    """The upstream bridge has no shock or downstream physical closure."""

    return False

  @property
  def physical_termination(self) -> bool:
    """Whether the retained decision is a verified physical chain stop."""

    return self.termination.physical_termination

  @property
  def chain_promotion_blocked(self) -> bool:
    """Prevent the bounded caustic bridge from becoming a chain cell."""

    return True

  @property
  def production_claim_allowed(self) -> bool:
    """Planner and research continuation results cannot support product claims."""

    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'branch_audit_verified': self.branch_audit_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination': self.physical_termination,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': self.termination.as_report(),
      'branch_audit': self.branch_audit.as_report(),
      'continuation': self.continuation.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


def plan_first_cell_free_boundary_correction(
  correction: MocFirstCellFreeBoundaryCorrectionResult,
  *,
  claim_status: str | None = None,
) -> MocFirstCellFreeBoundaryCorrectionPlannerResult:
  """Expose a corrected first cell through the planner safety boundary.

  The correction owns the numerical result and its termination decision.  The
  planner records that decision without invoking a continued-cell callback;
  only a later canonical reflected free-boundary gate may authorize such a
  handoff.
  """

  if not isinstance(
    correction,
    MocFirstCellFreeBoundaryCorrectionResult,
  ):
    raise TypeError(
      'correction must be a MocFirstCellFreeBoundaryCorrectionResult'
    )
  termination = correction.as_chain_termination_decision()
  return MocFirstCellFreeBoundaryCorrectionPlannerResult(
    correction=correction,
    termination=termination,
    planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
    claim_status=(
      'solver-generated-first-cell-free-boundary-correction-guard; '
      'continued-cell-promotion-and-canonical-reflected-free-boundary-pending'
      if claim_status is None
      else claim_status
    ),
    diagnostics={
      'planner_model': 'first-cell-free-boundary-correction-guard',
      'continued_cell_callback_invoked': False,
      'correction_status': correction.status.value,
      'correction_decision_reason': termination.reason.value,
      'chain_promotion_blocked': correction.chain_promotion_blocked,
      'canonical_free_boundary_verified': (
        correction.canonical_free_boundary_verified
      ),
      'canonical_euler_verified': correction.canonical_euler_verified,
      'external_validation_verified': correction.external_validation_verified,
    },
  )


def plan_first_cell_terminal_closure(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
  control_section: MocMixedRegimeControlSection | None = None,
  solve_field: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeFieldResult | None,
  ] | None = None,
  use_integrated_flux: bool = False,
  mixed_regime_entropy_source_arc_length_m: Sequence[float] | None = None,
  mixed_regime_entropy_streamline_ids: Sequence[int] | None = None,
  claim_status: str | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Audit a first-cell terminal and optionally submit its exact scalar seam.

  ``mock`` is the reusable rectangular pressure-outflow fixture.  ``solver``
  is the separate solver-owned quasi-one-dimensional free-boundary reference;
  a future higher-fidelity downstream solver can instead be supplied as
  ``solve_field``.  In every case the terminal object owns the request and the
  real mixed-regime adapter owns seam acceptance.  Omitting all three only
  audits the already-solved supersonic terminal and preserves its open/
  physical decision.  ``control_section`` is accepted only with ``solver``;
  the default section-aware path refuses to collapse a varying scalar section
  into a one-dimensional height.  ``use_integrated_flux`` opts into the
  separately named distributed-flux quasi-one-dimensional reference and still
  blocks production/chain claims.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  if mock is not None and not isinstance(
    mock,
    MocPrescribedMixedRegimeClosureMock,
  ):
    raise TypeError(
      'mock must be a MocPrescribedMixedRegimeClosureMock or None'
    )
  if solver is not None and not isinstance(
    solver,
    MocSolverGeneratedMixedRegimeClosureReference,
  ):
    raise TypeError(
      'solver must be a MocSolverGeneratedMixedRegimeClosureReference or None'
    )
  if control_section is not None and not isinstance(
    control_section,
    MocMixedRegimeControlSection,
  ):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection or None'
    )
  if control_section is not None and solver is None:
    raise ValueError('control_section requires the solver-generated reference')
  if not isinstance(use_integrated_flux, bool):
    raise TypeError('use_integrated_flux must be a bool')
  if use_integrated_flux and control_section is None:
    raise ValueError('use_integrated_flux requires a control_section')
  if use_integrated_flux and solver is None:
    raise ValueError('use_integrated_flux requires the solver-generated reference')
  supplied_solvers = sum(
    value is not None for value in (mock, solver, solve_field)
  )
  if supplied_solvers > 1:
    raise ValueError('supply only one of mock, solver, or solve_field')
  if solve_field is not None and not callable(solve_field):
    raise TypeError('solve_field must be callable when supplied')
  if (
    mixed_regime_entropy_source_arc_length_m is None
  ) != (
    mixed_regime_entropy_streamline_ids is None
  ):
    raise ValueError(
      'mixed_regime_entropy_source_arc_length_m and '
      'mixed_regime_entropy_streamline_ids must be supplied together'
    )

  planner_kind = (
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
    if mock is not None
    else MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  )
  diagnostics: dict[str, Any] = {
    'planner_model': 'first-cell-terminal-closure-planner',
    'mixed_regime_solver_supplied': supplied_solvers == 1,
    'mixed_regime_closure_attached': False,
    'mixed_regime_entropy_handoff_requested': False,
    'mixed_regime_entropy_handoff_verified': False,
    'mixed_regime_entropy_handoff_measurement': None,
    'mixed_regime_entropy_transport_requested': (
      mixed_regime_entropy_source_arc_length_m is not None
    ),
    'mixed_regime_entropy_transport_verified': False,
    'mixed_regime_entropy_transport_measurement': None,
    'chain_promotion_blocked': terminal.chain_promotion_blocked,
    'terminal_physical_closure_verified': terminal.physical_closure_verified,
  }
  if mock is not None:
    diagnostics['prescribed_mixed_regime_closure_mock'] = mock.as_report()
  elif solver is not None:
    diagnostics['downstream_solver_model'] = solver.model
    diagnostics['solver_generated_mixed_regime_reference'] = solver.as_report()
    diagnostics['control_section_supplied'] = control_section is not None
    diagnostics['control_section_flux_mode'] = (
      'integrated-flux-quasi-1d-reference'
      if use_integrated_flux
      else 'terminal-equivalent-geometric-measure'
    )
    if control_section is not None:
      diagnostics['control_section'] = control_section.as_report()
  elif solve_field is not None:
    diagnostics['downstream_solver_model'] = 'caller-supplied-mixed-regime-solver'

  mixed_regime_entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None
  if terminal.terminal_field is None or not terminal.converged:
    diagnostics['mixed_regime_entropy_handoff_skipped'] = (
      'terminal does not expose a converged supersonic field and exact seam'
    )
  else:
    try:
      entropy_request = terminal.mixed_regime_perimeter_request()
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      diagnostics['mixed_regime_entropy_handoff_error'] = str(error)
    else:
      diagnostics['mixed_regime_entropy_handoff_requested'] = True
      (
        mixed_regime_entropy_handoff,
        entropy_measurement,
        entropy_verified,
        entropy_error,
      ) = _audit_mixed_regime_entropy_handoff(entropy_request)
      if entropy_measurement is not None:
        diagnostics['mixed_regime_entropy_handoff_measurement'] = (
          entropy_measurement
        )
      diagnostics['mixed_regime_entropy_handoff_verified'] = entropy_verified
      if entropy_error is not None:
        diagnostics['mixed_regime_entropy_handoff_error'] = entropy_error
      if mixed_regime_entropy_handoff is not None:
        diagnostics['mixed_regime_entropy_handoff'] = (
          mixed_regime_entropy_handoff.as_report()
        )

  mixed_regime_closure: MocMixedRegimeClosureResult | None = None
  attached_terminal = terminal
  if supplied_solvers == 1:
    if terminal.terminal_field is None or not terminal.converged:
      diagnostics['mixed_regime_solver_skipped'] = (
        'terminal does not expose a converged supersonic field and exact seam'
      )
    else:
      try:
        if mock is not None:
          mixed_regime_closure = mock.solve(
            terminal.mixed_regime_perimeter_request()
          )
        elif solver is not None:
          request = terminal.mixed_regime_perimeter_request()
          free_boundary = (
            solver.solve_from_control_section_flux(request, control_section)
            if use_integrated_flux
            else solver.solve_from_control_section(request, control_section)
            if control_section is not None
            else solver.solve(request)
          )
          diagnostics['solver_generated_mixed_regime_result'] = (
            free_boundary.as_report()
          )
          mixed_regime_closure = free_boundary.closure
          if mixed_regime_closure is None:
            diagnostics['mixed_regime_closure_message'] = free_boundary.message
        else:
          assert solve_field is not None
          mixed_regime_closure = terminal.solve_mixed_regime_closure(solve_field)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        diagnostics['mixed_regime_solver_error'] = str(error)
      else:
        diagnostics['mixed_regime_closure_status'] = (
          mixed_regime_closure.status.value
          if mixed_regime_closure is not None
          else 'solver-owned-free-boundary-no-closure'
        )
        if mixed_regime_closure is not None and mixed_regime_closure.converged:
          try:
            attached_terminal = terminal.attach_mixed_regime_closure(
              mixed_regime_closure
            )
          except (TypeError, ValueError) as error:
            diagnostics['mixed_regime_closure_attachment_error'] = str(error)
          else:
            diagnostics['mixed_regime_closure_attached'] = True
        elif mixed_regime_closure is not None:
          diagnostics['mixed_regime_closure_message'] = (
            mixed_regime_closure.message
          )

  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None
  if mixed_regime_entropy_source_arc_length_m is not None:
    if mixed_regime_entropy_handoff is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'entropy handoff was not available for the explicit source map'
      )
    elif mixed_regime_closure is None or mixed_regime_closure.field is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'mixed-regime solver did not return a scalar field for the explicit '
        'source map'
      )
    else:
      transport_request = mixed_regime_entropy_handoff.request
      if not isinstance(transport_request, MocMixedRegimePerimeterRequest):
        diagnostics['mixed_regime_entropy_transport_skipped'] = (
          'entropy handoff did not retain a typed perimeter request'
        )
      else:
        (
          mixed_regime_entropy_transport,
          transport_measurement,
          transport_verified,
          transport_error,
        ) = _audit_mixed_regime_entropy_transport(
          transport_request,
          mixed_regime_entropy_handoff,
          mixed_regime_closure.field,
          mixed_regime_entropy_source_arc_length_m,
          mixed_regime_entropy_streamline_ids or (),
        )
        diagnostics['mixed_regime_entropy_transport_verified'] = (
          transport_verified
        )
        if transport_measurement is not None:
          diagnostics['mixed_regime_entropy_transport_measurement'] = (
            transport_measurement
          )
        if transport_error is not None:
          diagnostics['mixed_regime_entropy_transport_error'] = transport_error
        if mixed_regime_entropy_transport is not None:
          diagnostics['mixed_regime_entropy_transport'] = (
            mixed_regime_entropy_transport.as_report()
          )

  try:
    termination = attached_terminal.as_chain_termination_decision()
  except ValueError as error:
    termination = None
    diagnostics['termination_decision_error'] = str(error)

  diagnostics.update({
    'terminal_physical_closure_verified': attached_terminal.physical_closure_verified,
    'physical_termination': bool(
      termination is not None and termination.physical_termination
    ),
  })
  return MocFirstCellTerminalClosurePlannerResult(
    terminal=attached_terminal,
    mixed_regime_closure=mixed_regime_closure,
    termination=termination,
    planner_kind=planner_kind,
    claim_status=(
      (
        'prescribed-mixed-regime-terminal-planner-mock; '
        'canonical-downstream-free-boundary-pending'
      )
      if mock is not None
      else (
        'solver-generated-mixed-regime-free-boundary-reference; '
        'canonical-reflected-moc-and-external-validation-pending'
      )
      if solver is not None
      else (
        'first-cell-terminal-closure-planner; '
        'canonical-downstream-free-boundary-and-external-validation-pending'
      )
      if claim_status is None
      else claim_status
    ),
    diagnostics=diagnostics,
    mixed_regime_entropy_handoff=mixed_regime_entropy_handoff,
    mixed_regime_entropy_transport=mixed_regime_entropy_transport,
  )


def plan_prescribed_first_cell_terminal_closure_mock(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Run the explicit prescribed mixed-regime terminal planner fixture."""

  fixture = (
    MocPrescribedMixedRegimeClosureMock() if mock is None else mock
  )
  return plan_first_cell_terminal_closure(terminal, mock=fixture)
  ####


def plan_solver_generated_first_cell_terminal_closure_reference(
  terminal: MocFirstCellTerminalClosureResult,
  *,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Run the solver-owned finite free-boundary planner reference."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None
    else solver
  )
  return plan_first_cell_terminal_closure(terminal, solver=reference)
  ####


def plan_solver_generated_first_cell_terminal_closure_reference_from_control_section(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  *,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Plan a first-cell closure from an explicit scalar control section."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None
    else solver
  )
  return plan_first_cell_terminal_closure(
    terminal,
    solver=reference,
    control_section=control_section,
  )
  ####


def plan_solver_generated_first_cell_terminal_closure_reference_from_control_section_flux(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  *,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Plan a first-cell closure from integrated scalar control-section flux."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None
    else solver
  )
  return plan_first_cell_terminal_closure(
    terminal,
    solver=reference,
    control_section=control_section,
    use_integrated_flux=True,
  )
  ####


def plan_first_cell_terminal_closure_with_planar_handoff(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  solve_field: MocMixedRegimePlanarFieldSolver,
  *,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
  mixed_regime_entropy_source_arc_length_m: Sequence[float] | None = None,
  mixed_regime_entropy_streamline_ids: Sequence[int] | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Audit a first cell against an explicit downstream planar handoff.

  This wrapper records a successful callback-owned planar handoff beside the
  first-cell result, but deliberately does not attach it to the terminal or
  issue a physical termination decision.  The current planar field value can
  represent a scalar reference mesh, so promotion must wait for a solver that
  proves the canonical reflected-MOC downstream field and free boundary.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  if (
    mixed_regime_entropy_source_arc_length_m is None
  ) != (
    mixed_regime_entropy_streamline_ids is None
  ):
    raise ValueError(
      'mixed_regime_entropy_source_arc_length_m and '
      'mixed_regime_entropy_streamline_ids must be supplied together'
    )
  request = terminal.mixed_regime_perimeter_request()
  handoff = run_mixed_regime_planar_field_solver(
    request,
    control_section,
    perimeter_spec,
    solve_field,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    normal_flux_tolerance=normal_flux_tolerance,
    solver_model=solver_model,
  )
  base = plan_first_cell_terminal_closure(terminal)
  diagnostics = dict(base.diagnostics)
  diagnostics.update({
    'mixed_regime_planar_handoff_verified': handoff.handoff_verified,
    'mixed_regime_planar_handoff': handoff.as_report(),
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_handoff_chain_promotion_blocked': (
      handoff.chain_promotion_blocked
    ),
    'mixed_regime_planar_handoff_physical_closure_verified': (
      handoff.physical_closure_verified
    ),
  })
  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None
  if mixed_regime_entropy_source_arc_length_m is not None:
    entropy_handoff = base.mixed_regime_entropy_handoff
    if entropy_handoff is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'entropy handoff was not available for the explicit source map'
      )
    elif handoff.field is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'planar handoff did not return a scalar field for the explicit source map'
      )
    else:
      (
        mixed_regime_entropy_transport,
        transport_measurement,
        transport_verified,
        transport_error,
      ) = _audit_mixed_regime_entropy_transport(
        request,
        entropy_handoff,
        handoff.field,
        mixed_regime_entropy_source_arc_length_m,
        mixed_regime_entropy_streamline_ids or (),
      )
      diagnostics['mixed_regime_entropy_transport_verified'] = (
        transport_verified
      )
      if transport_measurement is not None:
        diagnostics['mixed_regime_entropy_transport_measurement'] = (
          transport_measurement
        )
      if transport_error is not None:
        diagnostics['mixed_regime_entropy_transport_error'] = transport_error
      if mixed_regime_entropy_transport is not None:
        diagnostics['mixed_regime_entropy_transport'] = (
          mixed_regime_entropy_transport.as_report()
        )
  return replace(
    base,
    claim_status=(
      'explicit-planar-downstream-handoff-only; canonical-reflected-moc-'
      'free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
    mixed_regime_planar_handoff=handoff,
    mixed_regime_entropy_transport=mixed_regime_entropy_transport,
  )
  ####


def plan_first_cell_terminal_closure_with_planar_potential_reference(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  *,
  reference: MocMixedRegimePlanarPotentialReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Plan a first-cell terminal beside the built-in planar reference.

  The reference consumes the exact terminal request, explicit control section,
  and explicit closed perimeter.  Its converged field remains an adjacent
  research handoff: this wrapper never attaches it to the supersonic terminal
  or promotes it into a continued shock-cell chain.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  planar_reference = (
    MocMixedRegimePlanarPotentialReference()
    if reference is None
    else reference
  )
  if not isinstance(
    planar_reference,
    MocMixedRegimePlanarPotentialReference,
  ):
    raise TypeError(
      'reference must be a MocMixedRegimePlanarPotentialReference or None'
    )
  handoff = planar_reference.solve(
    terminal.mixed_regime_perimeter_request(),
    control_section,
    perimeter_spec,
  )
  base = plan_first_cell_terminal_closure(terminal)
  diagnostics = dict(base.diagnostics)
  diagnostics.update({
    'mixed_regime_planar_potential_reference': planar_reference.as_report(),
    'mixed_regime_planar_handoff_verified': handoff.handoff_verified,
    'mixed_regime_planar_handoff': handoff.as_report(),
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_handoff_chain_promotion_blocked': (
      handoff.chain_promotion_blocked
    ),
    'mixed_regime_planar_handoff_physical_closure_verified': (
      handoff.physical_closure_verified
    ),
    'mixed_regime_planar_projection_verified': (
      handoff.control_section_projection_verified
    ),
  })
  return replace(
    base,
    claim_status=(
      'control-section-projected-compressible-potential-reference; '
      'canonical-reflected-moc-free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
    mixed_regime_planar_handoff=handoff,
  )
  ####


def plan_first_cell_terminal_closure_with_planar_frozen_profile_reference(
  terminal: MocFirstCellTerminalClosureResult,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  *,
  reference: MocMixedRegimePlanarFrozenProfileReference | None = None,
) -> MocFirstCellTerminalClosurePlannerResult:
  """Plan a first cell beside the non-affine planar reference lane.

  The frozen-profile reference is intentionally an adjacent research result.
  This wrapper retains its exact request and profile diagnostics in planner
  evidence, but never attaches a scalar potential field to the supersonic
  terminal or promotes it into a continued shock-cell chain.
  """

  if not isinstance(terminal, MocFirstCellTerminalClosureResult):
    raise TypeError(
      'terminal must be a MocFirstCellTerminalClosureResult'
    )
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  planar_reference = (
    MocMixedRegimePlanarFrozenProfileReference()
    if reference is None
    else reference
  )
  if not isinstance(
    planar_reference,
    MocMixedRegimePlanarFrozenProfileReference,
  ):
    raise TypeError(
      'reference must be a MocMixedRegimePlanarFrozenProfileReference or None'
    )
  handoff = planar_reference.solve(
    terminal.mixed_regime_perimeter_request(),
    control_section,
    perimeter_spec,
  )
  base = plan_first_cell_terminal_closure(terminal)
  diagnostics = dict(base.diagnostics)
  diagnostics.update({
    'mixed_regime_planar_frozen_profile_reference': (
      planar_reference.as_report()
    ),
    'mixed_regime_planar_handoff_verified': handoff.handoff_verified,
    'mixed_regime_planar_handoff': handoff.as_report(),
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_handoff_chain_promotion_blocked': (
      handoff.chain_promotion_blocked
    ),
    'mixed_regime_planar_handoff_physical_closure_verified': (
      handoff.physical_closure_verified
    ),
    'mixed_regime_planar_projection_verified': (
      handoff.control_section_projection_verified
    ),
  })
  return replace(
    base,
    claim_status=(
      'control-section-frozen-profile-compressible-potential-reference; '
      'canonical-reflected-moc-free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
    mixed_regime_planar_handoff=handoff,
  )
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedPostShockChainMock:
  """Deterministic continued-cell fixture for planner and report validation.

  This fixture supplies a prescribed next-shock curve and therefore is not a
  free-boundary MOC solver.  It exists so the state-carrying planner contract
  can be exercised over more than one cell without making synthetic geometry
  eligible for a production plume claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.50
  shock_start_offset_m: float = 0.20
  shock_sample_spacing_m: float = 0.02
  shock_geometry_scale_per_cell: float = 0.0
  # The default line is tangent to a weak attached shock for M=2, gamma=1.4.
  # It is deliberately still prescribed geometry, but the local fit below now
  # proves that it is compatible with the requested attached-shock branch
  # before the field is assembled.  The varying downstream angles keep the
  # characteristic mesh nondegenerate.
  shock_ordinates_m: tuple[float, ...] = (
    0.08237108456402913,
    0.06177831342302184,
    0.04118554228201456,
    0.020592771141007285,
    0.0,
  )
  # Explicit normalized coordinates map the prior carried pressure trace to
  # the prescribed next-shock samples.  This remains a fixture mapping, not
  # a solved streamline/free-boundary relation.
  shock_pressure_coordinates: tuple[float, ...] | None = None
  downstream_flow_angles_rad: tuple[float, ...] = (-0.16, -0.12, -0.08, -0.04, 0.0)
  upstream_flow_angle_start_rad: float = -0.22316537247754467
  upstream_flow_angle_step_rad: float = 0.01953284223794056
  upstream_flow_angles_rad: tuple[float, ...] = (
    -0.22316537247754467,
    -0.204175961115758,
    -0.18482733549527713,
    -0.16511536988179235,
    -0.14503421352578244,
  )
  mach: float = 2.0
  gamma: float = 1.4
  pressure_loss_ratio: float | None = None
  # Optional schedules apply to continued cells 2..total_cell_count.  They
  # are explicit geometry controls for planner/visualization scenarios; they
  # do not turn this prescribed-boundary fixture into a free-boundary solver.
  cell_axial_lengths_m: tuple[float, ...] | None = None
  shock_start_offsets_m: tuple[float, ...] | None = None
  shock_geometry_scales_per_cell: tuple[float, ...] | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_sample_spacing_m', self.shock_sample_spacing_m),
    ):
      if not isfinite(float(value)) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if not isfinite(float(self.shock_geometry_scale_per_cell)):
      raise ValueError('shock_geometry_scale_per_cell must be finite')
    for name, value, lower_bound in (
      ('mach', self.mach, 1.0),
      ('gamma', self.gamma, 1.0),
    ):
      if not isfinite(float(value)) or value <= lower_bound:
        raise ValueError(f'{name} must be finite and greater than {lower_bound}')
    if self.pressure_loss_ratio is not None and (
      not isfinite(float(self.pressure_loss_ratio))
      or not 0.0 < self.pressure_loss_ratio < 1.0
    ):
      raise ValueError(
        'pressure_loss_ratio must be finite and strictly between zero and one '
        'when supplied'
      )
    try:
      ordinates = tuple(float(value) for value in self.shock_ordinates_m)
      downstream_angles = tuple(float(value) for value in self.downstream_flow_angles_rad)
    except (TypeError, ValueError) as error:
      raise ValueError('shock ordinates and downstream angles must be numeric sequences') from error
    if len(ordinates) < 3 or len(ordinates) != len(downstream_angles):
      raise ValueError(
        'shock ordinates and downstream angles must have equal lengths of at least three'
      )
    if any(not isfinite(value) or value < 0.0 for value in ordinates):
      raise ValueError('shock ordinates must be finite and nonnegative')
    if any(next_value > value for value, next_value in zip(ordinates, ordinates[1:])):
      raise ValueError('shock ordinates must be nonincreasing toward the centerline')
    if abs(ordinates[-1]) > 1.0e-12:
      raise ValueError('the final prescribed shock ordinate must be the centerline')
    if any(not isfinite(value) for value in downstream_angles):
      raise ValueError('downstream flow angles must be finite')
    if abs(downstream_angles[-1]) > 1.0e-12:
      raise ValueError('the final prescribed downstream flow angle must be zero')
    try:
      configured_pressure_coordinates = (
        tuple(float(value) for value in self.shock_pressure_coordinates)
        if self.shock_pressure_coordinates is not None
        else tuple(
          index / (len(ordinates) - 1)
          for index in range(len(ordinates))
        )
      )
    except (TypeError, ValueError) as error:
      raise ValueError(
        'shock_pressure_coordinates must be a numeric sequence'
      ) from error
    if len(configured_pressure_coordinates) != len(ordinates):
      raise ValueError(
        'shock_pressure_coordinates must match the shock sample count'
      )
    if any(
      not isfinite(value) or value < 0.0 or value > 1.0
      for value in configured_pressure_coordinates
    ):
      raise ValueError(
        'shock_pressure_coordinates must contain finite values in [0, 1]'
      )
    if (
      abs(configured_pressure_coordinates[0]) > 1.0e-12
      or abs(configured_pressure_coordinates[-1] - 1.0) > 1.0e-12
    ):
      raise ValueError(
        'shock_pressure_coordinates must start at zero and end at one'
      )
    if any(
      next_value <= value
      for value, next_value in zip(
        configured_pressure_coordinates,
        configured_pressure_coordinates[1:],
      )
    ):
      raise ValueError(
        'shock_pressure_coordinates must be strictly increasing'
      )
    for name, value in (
      ('upstream_flow_angle_start_rad', self.upstream_flow_angle_start_rad),
      ('upstream_flow_angle_step_rad', self.upstream_flow_angle_step_rad),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    try:
      configured_upstream_angles = (
        tuple(float(value) for value in self.upstream_flow_angles_rad)
        if self.upstream_flow_angles_rad is not None
        else tuple(
          float(self.upstream_flow_angle_start_rad)
          + float(self.upstream_flow_angle_step_rad) * index
          for index in range(len(downstream_angles))
        )
      )
    except (TypeError, ValueError) as error:
      raise ValueError('upstream_flow_angles_rad must be a numeric sequence') from error
    if len(configured_upstream_angles) != len(downstream_angles):
      raise ValueError(
        'upstream_flow_angles_rad must match the downstream angle sample count'
      )
    if any(not isfinite(value) for value in configured_upstream_angles):
      raise ValueError('upstream flow angles must be finite')
    if self.shock_geometry_scales_per_cell is None:
      for cell_index in range(2, self.total_cell_count + 1):
        scale = 1.0 + float(self.shock_geometry_scale_per_cell) * (cell_index - 2)
        if scale <= 0.0:
          raise ValueError(
            'shock_geometry_scale_per_cell produces a non-positive scale '
            f'at cell {cell_index}'
          )

    def normalize_schedule(
      values: tuple[float, ...] | None,
      name: str,
      *,
      positive: bool = True,
    ) -> tuple[float, ...] | None:
      if values is None:
        return None
      try:
        normalized = tuple(float(value) for value in values)
      except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a numeric sequence') from error
      expected_count = self.total_cell_count - 1
      if len(normalized) != expected_count:
        raise ValueError(
          f'{name} must contain one value for each continued cell '
          f'(expected {expected_count}, got {len(normalized)})'
        )
      if any(
        not isfinite(value) or (value <= 0.0 if positive else False)
        for value in normalized
      ):
        qualifier = 'finite and positive' if positive else 'finite'
        raise ValueError(f'{name} must contain {qualifier} values')
      return normalized

    normalized_lengths = normalize_schedule(
      self.cell_axial_lengths_m,
      'cell_axial_lengths_m',
    )
    normalized_offsets = normalize_schedule(
      self.shock_start_offsets_m,
      'shock_start_offsets_m',
    )
    normalized_scales = normalize_schedule(
      self.shock_geometry_scales_per_cell,
      'shock_geometry_scales_per_cell',
    )
    for cell_index in range(2, self.total_cell_count + 1):
      schedule_index = cell_index - 2
      axial_length = (
        float(self.cell_axial_length_m)
        if normalized_lengths is None
        else normalized_lengths[schedule_index]
      )
      start_offset = (
        float(self.shock_start_offset_m)
        if normalized_offsets is None
        else normalized_offsets[schedule_index]
      )
      scale = self._scheduled_scale_for_index(
        schedule_index,
        normalized_scales,
        float(self.shock_geometry_scale_per_cell),
      )
      shock_end_offset = (
        start_offset
        + float(self.shock_sample_spacing_m) * scale * (len(ordinates) - 1)
      )
      if shock_end_offset >= axial_length:
        raise ValueError(
          'continued-cell shock geometry must fit before the cell end: '
          f'cell {cell_index} ends at {axial_length} m but reaches '
          f'{shock_end_offset} m from its start'
        )
    object.__setattr__(self, 'shock_ordinates_m', ordinates)
    object.__setattr__(
      self,
      'shock_pressure_coordinates',
      configured_pressure_coordinates,
    )
    object.__setattr__(self, 'downstream_flow_angles_rad', downstream_angles)
    object.__setattr__(self, 'upstream_flow_angles_rad', configured_upstream_angles)
    object.__setattr__(self, 'cell_axial_lengths_m', normalized_lengths)
    object.__setattr__(self, 'shock_start_offsets_m', normalized_offsets)
    object.__setattr__(self, 'shock_geometry_scales_per_cell', normalized_scales)

  @property
  def sample_count(self) -> int:
    """Number of prescribed samples on each mock shock boundary."""

    return len(self.shock_ordinates_m)

  @staticmethod
  def _scheduled_scale_for_index(
    schedule_index: int,
    explicit_schedule: tuple[float, ...] | None,
    linear_step: float,
  ) -> float:
    """Resolve one scale during immutable configuration validation."""

    if explicit_schedule is not None:
      return explicit_schedule[schedule_index]
    return 1.0 + linear_step * schedule_index

  def _validate_continued_cell_index(self, cell_index: int) -> int:
    if (
      isinstance(cell_index, bool)
      or not isinstance(cell_index, int)
      or not 2 <= cell_index <= self.total_cell_count
    ):
      raise ValueError(
        'cell_index must identify a configured continued cell '
        f'(2 through {self.total_cell_count})'
      )
    return cell_index - 2

  def cell_axial_length_for_cell(self, cell_index: int) -> float:
    """Return the configured axial length for one continued cell."""

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.cell_axial_lengths_m is not None:
      return self.cell_axial_lengths_m[schedule_index]
    return float(self.cell_axial_length_m)

  def shock_start_offset_for_cell(self, cell_index: int) -> float:
    """Return the configured shock-start offset for one continued cell."""

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.shock_start_offsets_m is not None:
      return self.shock_start_offsets_m[schedule_index]
    return float(self.shock_start_offset_m)

  def shock_geometry_scale_for_cell(self, cell_index: int) -> float:
    """Return the deterministic geometry multiplier for one continued cell.

    The multiplier is a fixture control, not a solved shock-placement law.
    Keeping it behind a named method makes the scenario visible to report and
    visualization consumers while keeping the fidelity boundary explicit.
    """

    schedule_index = self._validate_continued_cell_index(cell_index)
    if self.shock_geometry_scales_per_cell is not None:
      scale = self.shock_geometry_scales_per_cell[schedule_index]
    else:
      scale = 1.0 + float(self.shock_geometry_scale_per_cell) * schedule_index
    if scale <= 0.0:
      raise ValueError(
        'shock_geometry_scale_per_cell produces a non-positive scale '
        f'at cell {cell_index}'
      )
    return scale

  def incoming_total_pressure_at_shock_samples(
    self,
    incoming_handoff: Sequence[MocChainBoundarySample],
  ) -> tuple[float, ...]:
    """Return the explicit pressure map used by the prescribed mock.

    The method is public so planner and visualization diagnostics can inspect
    the fixture's pressure-lineage policy without reaching into its solver
    callback.  It is still only a normalized reference mapping; it does not
    infer a physical streamline correspondence.
    """

    try:
      handoff = tuple(incoming_handoff)
    except TypeError as error:
      raise TypeError(
        'incoming_handoff must be an iterable of MocChainBoundarySample values'
      ) from error
    if any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    if len(handoff) < 2:
      raise ValueError(
        'incoming_handoff requires at least two pressure samples'
      )
    return self._map_incoming_total_pressure(handoff)

  def _map_incoming_total_pressure(
    self,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> tuple[float, ...]:
    """Map the prior pressure trace to the mock shock samples.

    The normalized coordinates are an explicit fixture policy.  They preserve
    pressure variation for contract tests without pretending that the
    prescribed shock has a physically derived mapping to the prior perimeter.
    """

    pressures = tuple(sample.total_pressure_Pa for sample in incoming_handoff)
    coordinates = self.shock_pressure_coordinates
    if coordinates is None:
      raise ValueError(
        'shock_pressure_coordinates was not normalized by the fixture'
      )
    last_incoming_index = len(pressures) - 1
    return tuple(
      (
        pressures[lower_index]
        if lower_index == upper_index
        else pressures[lower_index]
          + (pressures[upper_index] - pressures[lower_index]) * fraction
      )
      for coordinate in coordinates
      for position in (coordinate * last_incoming_index,)
      for lower_index in (int(position),)
      for upper_index in (min(lower_index + 1, last_incoming_index),)
      for fraction in (position - lower_index,)
    )

  def as_report(self) -> dict[str, Any]:
    """Return explicit provenance and configuration for the fixture."""

    return {
      'model': 'prescribed-post-shock-chain-planner-mock',
      'planning_only': True,
      'production_claim_allowed': False,
      'claim_fidelity_ceiling': (
        MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
      ),
      'boundary_provenance': (
        'prescribed-shock-ordinates-and-downstream-flow-angle-samples'
      ),
      'local_field_assembly': (
        'solver-backed-attached-shock-fit-and-post-shock-characteristic-field'
      ),
      'free_boundary_verified': False,
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_sample_spacing_m': self.shock_sample_spacing_m,
      'shock_geometry_scale_per_cell': self.shock_geometry_scale_per_cell,
      'shock_pressure_coordinates': self.shock_pressure_coordinates,
      'upstream_pressure_coordinate_model': (
        'explicit-normalized-shock-sample-coordinate-from-exact-incoming-handoff'
      ),
      'shock_geometry_scale_schedule': [
        {
          'cell_index': cell_index,
          'scale': self.shock_geometry_scale_for_cell(cell_index),
        }
        for cell_index in range(2, self.total_cell_count + 1)
      ],
      'cell_axial_lengths_m': self.cell_axial_lengths_m,
      'shock_start_offsets_m': self.shock_start_offsets_m,
      'shock_geometry_scales_per_cell': self.shock_geometry_scales_per_cell,
      'per_cell_geometry_schedule': [
        {
          'cell_index': cell_index,
          'axial_length_m': self.cell_axial_length_for_cell(cell_index),
          'shock_start_offset_m': self.shock_start_offset_for_cell(cell_index),
          'shock_geometry_scale': self.shock_geometry_scale_for_cell(cell_index),
        }
        for cell_index in range(2, self.total_cell_count + 1)
      ],
      'geometry_schedule_model': (
        'explicit-per-cell-schedule'
        if any(
          value is not None
          for value in (
            self.cell_axial_lengths_m,
            self.shock_start_offsets_m,
            self.shock_geometry_scales_per_cell,
          )
        )
        else 'global-values-with-linear-scale'
      ),
      'shock_ordinates_m': self.shock_ordinates_m,
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'upstream_flow_angle_start_rad': self.upstream_flow_angle_start_rad,
      'upstream_flow_angle_step_rad': self.upstream_flow_angle_step_rad,
      'upstream_flow_angles_rad': self.upstream_flow_angles_rad,
      'mach': self.mach,
      'gamma': self.gamma,
      'pressure_loss_ratio': self.pressure_loss_ratio,
      'pressure_loss_ratio_role': (
        'optional expected total-pressure ratio; never used to fabricate '
        'post-shock states'
      ),
      'upstream_pressure_model': (
        'normalized-index-resampling-of-exact-incoming-handoff'
      ),
      'claim_status': (
        'prescribed-next-shock-geometry-fixture; '
        'not-free-boundary-chain-evidence'
      ),
    }

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Return one deterministic mock cell or an explicit fixture stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if isinstance(next_cell_index, bool) or next_cell_index != current.cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if len(handoff) < 3:
      raise ValueError('incoming_handoff requires at least three state samples')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'prescribed post-shock chain planner mock exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )
    upstream_total_pressures = self.incoming_total_pressure_at_shock_samples(
      handoff
    )
    shock_geometry_scale = self.shock_geometry_scale_for_cell(next_cell_index)
    shock_start_x_m = current.end_x_m + self.shock_start_offset_for_cell(next_cell_index)
    shock_points = tuple(
      (
        shock_start_x_m
        + self.shock_sample_spacing_m * shock_geometry_scale * index,
        ordinate * shock_geometry_scale,
      )
      for index, ordinate in enumerate(self.shock_ordinates_m)
    )
    upstream_angles = self.upstream_flow_angles_rad
    if upstream_angles is None:
      raise ValueError('upstream_flow_angles_rad was not normalized by the fixture')
    upstream_states = tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=upstream_angles[index],
        mach=self.mach,
        gamma=self.gamma,
      )
      for index, point in enumerate(shock_points)
    )
    isentropic_factor = (
      1.0 + 0.5 * (self.gamma - 1.0) * self.mach**2
    ) ** (self.gamma / (self.gamma - 1.0))
    upstream_static_pressures = tuple(
      pressure / isentropic_factor
      for pressure in upstream_total_pressures
    )
    fit = fit_attached_shock_boundary(
      upstream_states,
      upstream_static_pressures,
      shock_points,
      self.downstream_flow_angles_rad,
      branch=ShockBranch.WEAK,
    )
    if not fit.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock rejected its shock geometry '
        f'with the local attached-shock fit: {fit.message}'
      )
    # Use the solver-backed fit as the source of truth for the characteristic
    # field.  This prevents the mock from silently fabricating zero residuals
    # or a total-pressure loss across a cell.
    if any(
      abs(angle - fitted.state.theta_rad) > 1.0e-12
      for angle, fitted in zip(
        self.downstream_flow_angles_rad,
        fit.boundary_states,
        strict=True,
      )
    ):
      raise ValueError(
        'prescribed post-shock chain planner mock fit changed its requested '
        'downstream flow angles'
      )
    if self.pressure_loss_ratio is not None:
      fitted_pressure_ratios = tuple(
        sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
        for sample in fit.boundary_states
      )
      if any(
        abs(ratio - self.pressure_loss_ratio) > 1.0e-8
        for ratio in fitted_pressure_ratios
      ):
        raise ValueError(
          'prescribed pressure_loss_ratio disagrees with the attached-shock '
          'fit; omit it to accept solver-computed pressure loss'
        )
    field = assemble_post_shock_characteristic_field(
      fit,
      incoming_handoff=handoff,
    )
    if not field.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock produced a non-converged '
        f'field: {field.message}'
      )
    return MocPostShockChainCellSolve(
      field=field,
      end_x_m=current.end_x_m + self.cell_axial_length_for_cell(next_cell_index),
    )


@dataclass(frozen=True, slots=True)
class MocSolverGeneratedPostShockChainReference:
  """Deterministic solver-generated reference for a continued MOC chain.

  Each step uses the real marched attached-shock solver and the real closed
  post-shock characteristic-field assembler.  The upstream state and the
  downstream turn law are deliberately simple, explicit reference inputs;
  they are not a reflected-plume free-boundary solution.  Keeping this
  reference beside the prescribed mock makes the distinction executable:
  both can exercise the chain handoff, but neither may raise a production
  provider claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.80
  shock_start_offset_m: float = 0.20
  shock_start_y_m: float = 0.50
  sample_count: int = 9
  mach: float = 2.0
  gamma: float = 1.4
  upstream_flow_angle_rad: float = -0.20
  downstream_flow_angle_scale_rad_per_m: float = 0.10
  target_centerline_y_m: float = 0.0
  branch: ShockBranch = ShockBranch.WEAK

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_start_y_m', self.shock_start_y_m),
      ('mach', self.mach),
      ('gamma', self.gamma),
      ('upstream_flow_angle_rad', self.upstream_flow_angle_rad),
      (
        'downstream_flow_angle_scale_rad_per_m',
        self.downstream_flow_angle_scale_rad_per_m,
      ),
      ('target_centerline_y_m', self.target_centerline_y_m),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    if self.cell_axial_length_m <= 0.0:
      raise ValueError('cell_axial_length_m must be finite and positive')
    if self.shock_start_offset_m <= 0.0:
      raise ValueError('shock_start_offset_m must be finite and positive')
    if self.shock_start_y_m <= 0.0:
      raise ValueError('shock_start_y_m must be finite and positive')
    if self.shock_start_y_m <= self.target_centerline_y_m:
      raise ValueError(
        'shock_start_y_m must be strictly above target_centerline_y_m'
      )
    if self.mach <= 1.0:
      raise ValueError('mach must be finite and greater than one')
    if self.gamma <= 1.0:
      raise ValueError('gamma must be finite and greater than one')
    if not isinstance(self.branch, ShockBranch):
      raise ValueError('branch must be a ShockBranch')

  def as_report(self) -> dict[str, Any]:
    """Return configuration and the explicit research-only claim ceiling."""

    return {
      'model': 'solver-generated-post-shock-chain-reference',
      'planning_only': True,
      'production_claim_allowed': False,
      'claim_fidelity_ceiling': (
        MocChainGeometryFidelity.RESOLVED_PLANAR_MOC.value
      ),
      'free_boundary_verified': False,
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_start_y_m': self.shock_start_y_m,
      'target_centerline_y_m': self.target_centerline_y_m,
      'sample_count': self.sample_count,
      'mach': self.mach,
      'gamma': self.gamma,
      'upstream_flow_angle_rad': self.upstream_flow_angle_rad,
      'downstream_flow_angle_scale_rad_per_m': (
        self.downstream_flow_angle_scale_rad_per_m
      ),
      'branch': self.branch.value,
      'upstream_state_model': 'uniform-explicit-reference-state',
      'upstream_pressure_model': (
        'normalized-shock-height-resampling-of-exact-incoming-handoff'
      ),
      'downstream_condition_model': 'linear-explicit-reference-turn-law',
      'claim_status': (
        'solver-generated-shock-and-closed-post-shock-field-reference; '
        'reflected-upstream-coupling-and-physical-boundary-pending'
      ),
    }

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Solve one reference cell from the exact prior state/pressure handoff."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if len(handoff) < 3:
      raise ValueError('incoming_handoff requires at least three state samples')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'solver-generated post-shock reference exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )

    incoming_total_pressure_trace = self._resample_incoming_total_pressure(handoff)
    isentropic_factor = (
      1.0 + 0.5 * (self.gamma - 1.0) * self.mach * self.mach
    ) ** (self.gamma / (self.gamma - 1.0))
    shock_start = (
      current.end_x_m + self.shock_start_offset_m,
      self.shock_start_y_m,
    )
    result = solve_marched_attached_shock_chain_cell(
      current,
      next_cell_index,
      handoff,
      start_point_m=shock_start,
      end_x_m=current.end_x_m + self.cell_axial_length_m,
      upstream_state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=self.upstream_flow_angle_rad,
        mach=self.mach,
        gamma=self.gamma,
      ),
      upstream_pressure_at=lambda point: (
        self._upstream_pressure_at(
          point,
          incoming_total_pressure_trace,
        ) / isentropic_factor
      ),
      target_centerline_y_m=self.target_centerline_y_m,
      downstream_flow_angle_at=(
        lambda _index, point: (
          self.downstream_flow_angle_scale_rad_per_m * point[1]
        )
      ),
      sample_count=self.sample_count,
      branch=self.branch,
    )
    return result

  def _resample_incoming_total_pressure(
    self,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> tuple[float, ...]:
    """Resample the complete prior pressure trace for this reference solve.

    The reference has no physical mapping from the prior perimeter to the
    next shock.  Normalized-index interpolation is therefore retained as an
    explicit fixture policy, but it preserves pressure variation instead of
    collapsing the handoff to its maximum value.
    """

    pressures = tuple(sample.total_pressure_Pa for sample in incoming_handoff)
    if len(pressures) == self.sample_count:
      return pressures
    last_incoming_index = len(pressures) - 1
    last_shock_index = self.sample_count - 1
    return tuple(
      (
        pressures[lower_index]
        if lower_index == upper_index
        else pressures[lower_index]
        + (pressures[upper_index] - pressures[lower_index]) * fraction
      )
      for index in range(self.sample_count)
      for position in (index * last_incoming_index / last_shock_index,)
      for lower_index in (int(position),)
      for upper_index in (min(lower_index + 1, last_incoming_index),)
      for fraction in (position - lower_index,)
    )

  def _upstream_pressure_at(
    self,
    point: tuple[float, float],
    incoming_total_pressure_trace: tuple[float, ...],
  ) -> float:
    """Return a height-interpolated pressure from the preserved handoff."""

    span = self.shock_start_y_m - self.target_centerline_y_m
    normalized_height = (
      self.shock_start_y_m - float(point[1])
    ) / span
    normalized_height = min(1.0, max(0.0, normalized_height))
    position = normalized_height * (len(incoming_total_pressure_trace) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(incoming_total_pressure_trace) - 1)
    fraction = position - lower_index
    return (
      incoming_total_pressure_trace[lower_index]
      + (
        incoming_total_pressure_trace[upper_index]
        - incoming_total_pressure_trace[lower_index]
      ) * fraction
    )


@dataclass(frozen=True, slots=True)
class MocFieldCoupledPostShockChainReference:
  """Deterministic reference for continuation fed by the prior solved field.

  This reference deliberately differs from
  :class:`MocSolverGeneratedPostShockChainReference`: its upstream state and
  pressure are sampled from the currently accepted bounded
  ``MocPostShockCharacteristicFieldResult``.  The start point, axial step,
  and downstream turn law remain explicit reference conditions.  A finite
  field boundary therefore becomes a typed stop instead of an opportunity to
  fall back to a uniform state.

  The class is a research/planner fixture.  It does not claim that the
  supplied field is the canonical reflected upstream plume domain.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.40
  shock_start_offset_m: float = 0.02
  shock_start_y_m: float = 0.05
  target_centerline_y_m: float = 0.0
  sample_count: int = 9
  downstream_flow_angle_scale_rad_per_m: float = 2.40
  branch: ShockBranch = ShockBranch.WEAK

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_start_y_m', self.shock_start_y_m),
      ('target_centerline_y_m', self.target_centerline_y_m),
      (
        'downstream_flow_angle_scale_rad_per_m',
        self.downstream_flow_angle_scale_rad_per_m,
      ),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    if self.cell_axial_length_m <= 0.0:
      raise ValueError('cell_axial_length_m must be finite and positive')
    if self.shock_start_offset_m <= 0.0:
      raise ValueError('shock_start_offset_m must be finite and positive')
    if self.shock_start_y_m <= self.target_centerline_y_m:
      raise ValueError(
        'shock_start_y_m must be strictly above target_centerline_y_m'
      )
    if self.downstream_flow_angle_scale_rad_per_m <= 0.0:
      raise ValueError(
        'downstream_flow_angle_scale_rad_per_m must be finite and positive'
      )
    if not isinstance(self.branch, ShockBranch):
      raise ValueError('branch must be a ShockBranch')

  def as_report(self) -> dict[str, Any]:
    """Return the explicit bounded-field reference configuration."""

    return {
      'model': 'field-coupled-post-shock-chain-reference',
      'planning_only': True,
      'production_claim_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_start_y_m': self.shock_start_y_m,
      'target_centerline_y_m': self.target_centerline_y_m,
      'sample_count': self.sample_count,
      'downstream_flow_angle_scale_rad_per_m': (
        self.downstream_flow_angle_scale_rad_per_m
      ),
      'branch': self.branch.value,
      'upstream_state_model': 'bounded-previous-post-shock-field',
      'upstream_pressure_model': 'bounded-previous-post-shock-field',
      'downstream_condition_model': 'linear-explicit-reference-turn-law',
      'claim_status': (
        'field-coupled-research-reference; canonical-reflected-domain-and-'
        'physical-downstream-boundary-pending'
      ),
    }

  def start_point_at(
    self,
    _field: MocPostShockCharacteristicFieldResult,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> tuple[float, float]:
    """Choose the next reference shock start downstream of the current cell."""

    return (
      current.end_x_m + self.shock_start_offset_m,
      self.shock_start_y_m,
    )

  def end_x_at(
    self,
    _field: MocPostShockCharacteristicFieldResult,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> float:
    """Return the deterministic axial endpoint for one reference cell."""

    return current.end_x_m + self.cell_axial_length_m

  def downstream_flow_angle_at(
    self,
    _index: int,
    point_m: tuple[float, float],
  ) -> float:
    """Return the explicit linear turn law, zero at the target centerline."""

    return self.downstream_flow_angle_scale_rad_per_m * (
      point_m[1] - self.target_centerline_y_m
    )

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
    upstream_field: MocPostShockCharacteristicFieldResult,
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Solve one cell from the exact bounded prior field, or return a stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or not isinstance(next_cell_index, int)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'field-coupled post-shock reference exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )
    return solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      upstream_field,
      start_point_m=self.start_point_at(
        upstream_field,
        current,
        next_cell_index,
      ),
      end_x_m=self.end_x_at(upstream_field, current, next_cell_index),
      target_centerline_y_m=self.target_centerline_y_m,
      downstream_flow_angle_at=self.downstream_flow_angle_at,
      sample_count=self.sample_count,
      branch=self.branch,
    )


@dataclass(frozen=True, slots=True)
class MocBoundedUpstreamFieldSource:
  """Bounded state/pressure callbacks for a solver-owned next-cell solve.

  The source is deliberately smaller than a closed physical field.  A future
  reflected-domain remesher or new-characteristic-family solver can expose its
  finite state domain through this object without pretending that the source
  is already a closed shock cell.  Every callback remains domain-bounded: it
  must return ``None`` outside the solved source domain rather than extrapolate
  a last state.
  """

  state_at: Callable[[tuple[float, float]], CharacteristicState | None]
  static_pressure_at: Callable[[tuple[float, float]], float | None]
  model: str
  domain_x_extent_m: tuple[float, float] | None = None
  domain_y_extent_m: tuple[float, float] | None = None
  upstream_coupling_verified: bool = False
  preferred_start_point_m: tuple[float, float] | None = None

  def __post_init__(self) -> None:
    if not callable(self.state_at) or not callable(self.static_pressure_at):
      raise TypeError('bounded upstream source callbacks must be callable')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)
    if not isinstance(self.upstream_coupling_verified, bool):
      raise TypeError('upstream_coupling_verified must be a bool')
    if self.preferred_start_point_m is not None:
      try:
        preferred_start = (
          float(self.preferred_start_point_m[0]),
          float(self.preferred_start_point_m[1]),
        )
      except (IndexError, TypeError, ValueError) as error:
        raise ValueError(
          'preferred_start_point_m must contain two finite coordinates'
        ) from error
      if not all(isfinite(value) for value in preferred_start):
        raise ValueError(
          'preferred_start_point_m must contain two finite coordinates'
        )
      object.__setattr__(self, 'preferred_start_point_m', preferred_start)
    for name in ('domain_x_extent_m', 'domain_y_extent_m'):
      extent = getattr(self, name)
      if extent is None:
        continue
      try:
        normalized = (float(extent[0]), float(extent[1]))
      except (IndexError, TypeError, ValueError) as error:
        raise ValueError(f'{name} must contain two finite coordinates') from error
      if (
        not all(isfinite(value) for value in normalized)
        or normalized[1] < normalized[0]
      ):
        raise ValueError(f'{name} must contain an ordered finite extent')
      object.__setattr__(self, name, normalized)
  ####

  @classmethod
  def from_physical_field(
    cls,
    field: MocPhysicalPostShockFieldResult,
  ) -> 'MocBoundedUpstreamFieldSource':
    """Expose an accepted physical field as a finite source-domain adapter."""

    if not isinstance(field, MocPhysicalPostShockFieldResult):
      raise TypeError('field must be a MocPhysicalPostShockFieldResult')
    points = tuple(
      point
      for cell in field.cells
      for point in cell.vertices_xr_m
    )
    x_extent = None
    y_extent = None
    if points:
      x_extent = (min(point[0] for point in points), max(point[0] for point in points))
      y_extent = (min(point[1] for point in points), max(point[1] for point in points))
    return cls(
      state_at=lambda point, field=field: field.state_at(point),
      static_pressure_at=lambda point, field=field: field.static_pressure_at(point),
      model='bounded-ambient-closed-physical-field',
      domain_x_extent_m=x_extent,
      domain_y_extent_m=y_extent,
      upstream_coupling_verified=field.upstream_shock_coupling_verified,
    )
  ####

  @classmethod
  def from_reflected_domain_remesh(
    cls,
    remesh: MocReflectedDomainRemeshResult,
    *,
    sample_position_tolerance_m: float = 1.0e-3,
    preferred_start_point_m: tuple[float, float] | None = None,
  ) -> 'MocBoundedUpstreamFieldSource':
    """Expose one converged reflected remesh as a bounded shock source.

    The remesh is an open Cauchy source field, not a closed shock cell.  This
    adapter therefore carries no upstream-shock-coupling claim and preserves
    the strip's finite interpolation domain.  A caller may override the
    preferred shock-start point only when it has an independently justified
    source location; the default is the first point on the newly supplied
    outer source curve.
    """

    if not isinstance(remesh, MocReflectedDomainRemeshResult):
      raise TypeError(
        'remesh must be a MocReflectedDomainRemeshResult'
      )
    if not remesh.state_sampling_available or remesh.source_strip is None:
      raise ValueError(
        'only a converged reflected-domain remesh with bounded state sampling '
        'can become an upstream source'
      )
    tolerance = float(sample_position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError(
        'sample_position_tolerance_m must be finite and positive'
      )
    strip = remesh.source_strip
    request = remesh.request
    if request is None or not request.outer_source_states:
      raise ValueError(
        'a converged reflected-domain remesh must retain its outer source curve'
      )
    points = tuple(
      (float(state.x_m), float(state.y_m))
      for state in (
        *strip.plus_source_states,
        *strip.minus_source_states,
      )
    )
    points = (*points, *(point for cell in strip.cells for point in cell.vertices_xr_m))
    x_extent = None
    y_extent = None
    if points:
      x_extent = (
        min(point[0] for point in points),
        max(point[0] for point in points),
      )
      y_extent = (
        min(point[1] for point in points),
        max(point[1] for point in points),
      )
    preferred_start = (
      request.outer_source_states[0].x_m,
      request.outer_source_states[0].y_m,
    ) if preferred_start_point_m is None else preferred_start_point_m
    return cls(
      state_at=lambda point, strip=strip, tolerance=tolerance: strip.state_at(
        point,
        position_tolerance_m=tolerance,
      ),
      static_pressure_at=lambda point, strip=strip, tolerance=tolerance: strip.static_pressure_at(
        point,
        position_tolerance_m=tolerance,
      ),
      model='bounded-reflected-domain-cauchy-remesh',
      domain_x_extent_m=x_extent,
      domain_y_extent_m=y_extent,
      upstream_coupling_verified=False,
      preferred_start_point_m=preferred_start,
    )
  ####

  @classmethod
  def from_terminal_reflection_patch(
    cls,
    patch: MocTerminalReflectionPatchResult,
    *,
    sample_position_tolerance_m: float = 1.0e-3,
  ) -> 'MocBoundedUpstreamFieldSource':
    """Expose a converged reflected patch as a finite upstream source."""

    if not isinstance(patch, MocTerminalReflectionPatchResult):
      raise TypeError(
        'patch must be a MocTerminalReflectionPatchResult'
      )
    if not patch.converged:
      raise ValueError(
        'only a converged terminal reflection patch can become an upstream source'
      )
    tolerance = float(sample_position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError(
        'sample_position_tolerance_m must be finite and positive'
      )
    points = tuple(
      point
      for cell in patch.cells
      for point in cell.vertices_xr_m
    )
    points = (*points, *patch.outgoing_trace_points_m, *patch.axis_points_m)
    x_extent = None
    y_extent = None
    if points:
      x_extent = (min(point[0] for point in points), max(point[0] for point in points))
      y_extent = (min(point[1] for point in points), max(point[1] for point in points))
    preferred_start = (
      patch.outgoing_trace_points_m[0]
      if patch.outgoing_trace_points_m
      else None
    )
    return cls(
      state_at=lambda point, patch=patch, tolerance=tolerance: patch.state_at(
        point,
        position_tolerance_m=tolerance,
      ),
      static_pressure_at=lambda point, patch=patch, tolerance=tolerance: patch.static_pressure_at(
        point,
        position_tolerance_m=tolerance,
      ),
      model='bounded-terminal-reflection-patch',
      domain_x_extent_m=x_extent,
      domain_y_extent_m=y_extent,
      upstream_coupling_verified=False,
      preferred_start_point_m=preferred_start,
    )
  ####

  @classmethod
  def from_caustic_upstream_bridge(
    cls,
    bridge: MocCausticUpstreamBridge,
    *,
    sample_position_tolerance_m: float = 1.0e-3,
    preferred_start_point_m: tuple[float, float] | None = None,
  ) -> 'MocBoundedUpstreamFieldSource':
    """Expose a converged old/new-family bridge as a bounded source.

    The bridge remains authoritative for branch selection and domain gaps.
    This adapter only supplies the callback shape consumed by the generic
    shock-chain reference; it does not turn the open caustic band into a
    closed cell or mark upstream coupling as physically verified.
    """

    if not isinstance(bridge, MocCausticUpstreamBridge):
      raise TypeError('bridge must be a MocCausticUpstreamBridge')
    if not bridge.fields_converged:
      raise ValueError(
        'only a bridge with converged old and restarted fields can become '
        'an upstream source'
      )
    tolerance = float(sample_position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError(
        'sample_position_tolerance_m must be finite and positive'
      )
    points = tuple(
      (float(point[0]), float(point[1]))
      for field in (bridge.old_family, bridge.restarted_family)
      for cell in field.cells
      for point in cell.vertices_xr_m
    )
    x_extent = None
    y_extent = None
    if points:
      x_extent = (min(point[0] for point in points), max(point[0] for point in points))
      y_extent = (min(point[1] for point in points), max(point[1] for point in points))
    return cls(
      state_at=lambda point, bridge=bridge, tolerance=tolerance: bridge.state_at(
        point,
        position_tolerance_m=tolerance,
      ),
      static_pressure_at=lambda point, bridge=bridge, tolerance=tolerance: bridge.static_pressure_at(
        point,
        position_tolerance_m=tolerance,
      ),
      model='bounded-caustic-upstream-bridge',
      domain_x_extent_m=x_extent,
      domain_y_extent_m=y_extent,
      upstream_coupling_verified=False,
      preferred_start_point_m=preferred_start_point_m,
    )
  ####

  def as_report(self) -> dict[str, Any]:
    """Serialize source provenance without serializing callback objects."""

    return {
      'model': self.model,
      'state_sampling_available': True,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'domain_x_extent_m': self.domain_x_extent_m,
      'domain_y_extent_m': self.domain_y_extent_m,
      'extrapolation_allowed': False,
      'preferred_start_point_m': self.preferred_start_point_m,
    }
  ####


def build_terminal_reflection_patch_upstream_source(
  field: MocPhysicalPostShockFieldResult,
  *,
  trace_position_tolerance_m: float = 1.0e-3,
  trace_invariant_tolerance: float = 1.0e-10,
  sample_position_tolerance_m: float = 1.0e-3,
) -> MocBoundedUpstreamFieldSource | MocChainTerminationDecision:
  """Build the solver-owned reflected-patch source for a next shock.

  The returned source is bounded by the accepted field's terminal reflection
  patch.  A failed projection is a typed physical-closure stop, never a
  fallback to the whole closed field or an extrapolated state.
  """

  if not isinstance(field, MocPhysicalPostShockFieldResult):
    raise TypeError('field must be a MocPhysicalPostShockFieldResult')
  try:
    strip = field.as_open_shock_ambient_strip(
      trace_position_tolerance_m=trace_position_tolerance_m,
      trace_invariant_tolerance=trace_invariant_tolerance,
    )
    patch = assemble_terminal_trace_centerline_patch(
      strip,
      trace_position_tolerance_m=trace_position_tolerance_m,
      invariant_tolerance=trace_invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'accepted physical field could not produce a bounded terminal '
        f'reflection-patch upstream source: {error}'
      ),
      diagnostics={
        'termination_model': 'terminal-reflection-patch-source-projection',
        'source_projection_status': 'failed',
        'source_projection_error': type(error).__name__,
      },
    )
  if not patch.converged:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'terminal reflection patch did not converge; no next-cell upstream '
        f'source was promoted: {patch.message}'
      ),
      diagnostics={
        'termination_model': 'terminal-reflection-patch-source-projection',
        'source_projection_status': patch.status.value,
        'source_strip_status': patch.source_strip_status.value if patch.source_strip_status is not None else None,
        'reflection_patch': patch.as_report(),
      },
    )
  return MocBoundedUpstreamFieldSource.from_terminal_reflection_patch(
    patch,
    sample_position_tolerance_m=sample_position_tolerance_m,
  )
####


@dataclass(frozen=True, slots=True)
class MocSolverGeneratedAmbientClosedPostShockChainReference:
  """Research planner for repeated solver-generated physical cells.

  The planner owns the repeated call to the ambient-attachment and explicit
  centerline-reflection physical-field solver.  It does not own the missing
  downstream upstream-domain solve: ``upstream_source_provider`` must return
  a bounded source produced by a reflected-domain remesher, new-family
  continuation, or an explicitly named reference fixture.  When no provider
  is supplied, ``upstream_source_mode`` selects either the prior closed field
  or the solver-owned terminal-reflection-patch source.  The default
  prior-field mode preserves the finite-domain ``UPSTREAM_FIELD_BOUNDARY``
  behavior; reflected-patch mode makes the next physical continuation attempt
  without requiring a manually wired callback.

  A returned field replaces the active chain source only after all physical
  field gates and the exact incoming centerline handoff pass.  This is a
  continuation/research lane and cannot authorize a product-provider claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.40
  shock_start_offset_m: float = 0.02
  shock_start_y_m: float = 0.50
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  ambient_pressure_Pa: float = 101325.0
  outer_downstream_flow_angle_lower_rad: float = 0.02
  outer_downstream_flow_angle_upper_rad: float = 0.12
  sample_count: int = 9
  branch: ShockBranch = ShockBranch.WEAK
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  attachment_pressure_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  shock_angle_tolerance_rad: float = 1.0e-2
  maximum_segment_iterations: int = 24
  maximum_boundary_iterations: int = 16
  maximum_shooting_iterations: int = 40
  upstream_source_mode: MocAmbientClosedChainSourceMode = (
    MocAmbientClosedChainSourceMode.PREVIOUS_FIELD
  )
  source_trace_position_tolerance_m: float = 1.0e-3
  source_sample_position_tolerance_m: float = 1.0e-3
  upstream_source_provider: Callable[
    [
      MocPhysicalPostShockFieldResult,
      MocChainCell,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocBoundedUpstreamFieldSource | MocChainTerminationDecision | None,
  ] | None = None
  model: str = 'solver-generated-ambient-closed-post-shock-chain-reference'

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    if not isinstance(
      self.upstream_source_mode,
      MocAmbientClosedChainSourceMode,
    ):
      raise TypeError(
        'upstream_source_mode must be a MocAmbientClosedChainSourceMode'
      )
    for name in (
      'cell_axial_length_m',
      'shock_start_offset_m',
      'shock_start_y_m',
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'ambient_pressure_Pa',
      'outer_downstream_flow_angle_lower_rad',
      'outer_downstream_flow_angle_upper_rad',
      'position_tolerance_m',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
      'source_trace_position_tolerance_m',
      'source_sample_position_tolerance_m',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      object.__setattr__(self, name, value)
    if self.cell_axial_length_m <= 0.0:
      raise ValueError('cell_axial_length_m must be finite and positive')
    if self.shock_start_offset_m <= 0.0:
      raise ValueError('shock_start_offset_m must be finite and positive')
    if self.shock_start_y_m <= self.target_centerline_y_m:
      raise ValueError('shock_start_y_m must be above target_centerline_y_m')
    if self.ambient_pressure_Pa <= 0.0:
      raise ValueError('ambient_pressure_Pa must be finite and positive')
    if self.outer_downstream_flow_angle_lower_rad >= self.outer_downstream_flow_angle_upper_rad:
      raise ValueError(
        'outer downstream flow-angle lower bound must be below its upper bound'
      )
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
      'source_trace_position_tolerance_m',
      'source_sample_position_tolerance_m',
    ):
      if getattr(self, name) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    if (
      self.upstream_source_provider is not None
      and self.upstream_source_mode
      is not MocAmbientClosedChainSourceMode.PREVIOUS_FIELD
    ):
      raise ValueError(
        'upstream_source_provider cannot be combined with a non-default '
        'upstream_source_mode'
      )
    for name in (
      'maximum_segment_iterations',
      'maximum_boundary_iterations',
      'maximum_shooting_iterations',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
    if self.upstream_source_provider is not None and not callable(
      self.upstream_source_provider
    ):
      raise TypeError('upstream_source_provider must be callable when supplied')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)
  ####

  def as_report(self) -> dict[str, Any]:
    """Return the reference controls and its explicit fidelity ceiling."""

    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': False,
      'physical_chain_promotion_allowed': False,
      'free_boundary_verified': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_start_y_m': self.shock_start_y_m,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_downstream_flow_angle_bracket': (
        self.outer_downstream_flow_angle_lower_rad,
        self.outer_downstream_flow_angle_upper_rad,
      ),
      'sample_count': self.sample_count,
      'branch': self.branch.value,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'attachment_pressure_tolerance': self.attachment_pressure_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'upstream_source_mode': self.upstream_source_mode.value,
      'source_trace_position_tolerance_m': (
        self.source_trace_position_tolerance_m
      ),
      'source_sample_position_tolerance_m': (
        self.source_sample_position_tolerance_m
      ),
      'upstream_source_model': (
        'callback-supplied-bounded-source'
        if self.upstream_source_provider is not None
        else self.upstream_source_mode.value
      ),
      'upstream_source_contract': (
        'finite-state-pressure-callbacks; no extrapolation; exact handoff '
        'provided to source provider'
      ),
      'downstream_condition_model': (
        'ambient-attachment-shoot-plus-centerline-reflection'
      ),
      'claim_status': (
        'solver-generated-ambient-closed-chain-reference; reflected-upstream-'
        'remesher-and-external-validation-pending'
      ),
    }
  ####

  def start_point_at(
    self,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> tuple[float, float]:
    """Return the explicit local shock-start location for the next cell."""

    return (
      current.end_x_m + self.shock_start_offset_m,
      self.shock_start_y_m,
    )
  ####

  def end_x_at(
    self,
    current: MocChainCell,
    _next_cell_index: int,
  ) -> float:
    """Return the bookkeeping endpoint for one generated reference cell."""

    return current.end_x_m + self.cell_axial_length_m
  ####

  def _source_for(
    self,
    current_field: MocPhysicalPostShockFieldResult,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocBoundedUpstreamFieldSource | MocChainTerminationDecision | None:
    if self.upstream_source_provider is not None:
      return self.upstream_source_provider(
        current_field,
        current,
        next_cell_index,
        incoming_handoff,
      )
    if self.upstream_source_mode is MocAmbientClosedChainSourceMode.TERMINAL_REFLECTION_PATCH:
      return build_terminal_reflection_patch_upstream_source(
        current_field,
        trace_position_tolerance_m=self.source_trace_position_tolerance_m,
        trace_invariant_tolerance=self.invariant_tolerance,
        sample_position_tolerance_m=self.source_sample_position_tolerance_m,
      )
    return MocBoundedUpstreamFieldSource.from_physical_field(current_field)
  ####

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
    current_field: MocPhysicalPostShockFieldResult,
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    """Solve one generated physical cell or return a typed non-physical stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or not isinstance(next_cell_index, int)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    if not isinstance(current_field, MocPhysicalPostShockFieldResult):
      raise TypeError(
        'current_field must be a MocPhysicalPostShockFieldResult'
      )
    handoff = tuple(incoming_handoff)
    if handoff != current.continuation_boundary:
      raise ValueError(
        'incoming_handoff must exactly match current.continuation_boundary'
      )
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'solver-generated ambient-closed chain reference exhausted its '
          f'{self.total_cell_count}-cell fixture'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_cell_index': next_cell_index,
          'termination_model': 'configured-cell-count',
        },
      )

    end_x = self.end_x_at(current, next_cell_index)
    diagnostics: dict[str, Any] = {
      'continuation_model': self.model,
      'next_cell_index': next_cell_index,
      'end_x_m': end_x,
      'incoming_handoff_sample_count': len(handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
    }

    def decision(
      reason: MocChainTerminationReason,
      message: str,
      extra: dict[str, Any] | None = None,
    ) -> MocChainTerminationDecision:
      payload = dict(diagnostics)
      if extra is not None:
        payload.update(extra)
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=reason,
        message=message,
        diagnostics=payload,
      )

    try:
      source = self._source_for(
        current_field,
        current,
        next_cell_index,
        handoff,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return decision(
        MocChainTerminationReason.SOLVER_ERROR,
        f'bounded upstream source provider failed: {error}',
        {'source_provider_error': type(error).__name__},
      )
    if isinstance(source, MocChainTerminationDecision):
      source_diagnostics = dict(source.diagnostics)
      source_diagnostics.update({
        'upstream_source_provider_reason': source.reason.value,
        'upstream_source_provider_physical_termination': (
          source.physical_termination
        ),
      })
      if source.physical_termination:
        return decision(
          MocChainTerminationReason.INVALID_INPUT,
          (
            'upstream source provider returned a physical termination decision; '
            'only the downstream shock solve may declare plume termination'
          ),
          {
            **source_diagnostics,
            'source_provider_returned_physical_termination': True,
          },
        )
      source_diagnostics.update(diagnostics)
      return replace(source, diagnostics=source_diagnostics)
    if source is None:
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'upstream source provider returned no bounded next-cell field',
        {'source_provider_returned': None},
      )
    if not isinstance(source, MocBoundedUpstreamFieldSource):
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        'upstream source provider must return MocBoundedUpstreamFieldSource, '
        'MocChainTerminationDecision, or None',
        {'source_provider_returned_type': type(source).__name__},
      )
    diagnostics['upstream_source'] = source.as_report()
    preferred_start = source.preferred_start_point_m
    start = (
      self.start_point_at(current, next_cell_index)
      if preferred_start is None
      else preferred_start
    )
    diagnostics['start_point_provenance'] = (
      'reference-offset' if preferred_start is None else 'bounded-source-preferred'
    )
    diagnostics['start_point_m'] = start
    if preferred_start is not None and (
      preferred_start[0] < current.end_x_m - self.position_tolerance_m
    ):
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'bounded upstream source preferred shock start is upstream of the current cell interface; no backtracking or extrapolation was performed',
        {
          'preferred_start_point_m': preferred_start,
          'current_cell_end_x_m': current.end_x_m,
          'start_point_downstream_of_current_cell': False,
        },
      )
    diagnostics['start_point_downstream_of_current_cell'] = True

    try:
      start_state = source.state_at(start)
      start_pressure = source.static_pressure_at(start)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return decision(
        MocChainTerminationReason.SOLVER_ERROR,
        f'bounded upstream source failed at shock start: {error}',
        {'source_callback_error': type(error).__name__},
      )
    if start_state is None or start_pressure is None:
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'next-cell shock start is outside the bounded upstream source; no extrapolation was performed',
        {
          'first_missing_sample_index': 0,
          'candidate_point_m': start,
        },
      )
    if (
      not isinstance(start_state, CharacteristicState)
      or abs(start_state.x_m - start[0]) > self.position_tolerance_m
      or abs(start_state.y_m - start[1]) > self.position_tolerance_m
      or not isfinite(float(start_pressure))
      or float(start_pressure) <= 0.0
    ):
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'bounded upstream source returned an invalid shock-start state or pressure',
        {'candidate_point_m': start},
      )

    try:
      result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
        source.state_at,
        source.static_pressure_at,
        start,
        self.ambient_pressure_Pa,
        self.outer_downstream_flow_angle_lower_rad,
        self.outer_downstream_flow_angle_upper_rad,
        target_centerline_y_m=self.target_centerline_y_m,
        target_centerline_flow_angle_rad=self.target_centerline_flow_angle_rad,
        incoming_handoff=handoff,
        sample_count=self.sample_count,
        branch=self.branch,
        position_tolerance_m=self.position_tolerance_m,
        invariant_tolerance=self.invariant_tolerance,
        attachment_pressure_tolerance=self.attachment_pressure_tolerance,
        pressure_tolerance=self.pressure_tolerance,
        tangent_tolerance=self.tangent_tolerance,
        shock_angle_tolerance_rad=self.shock_angle_tolerance_rad,
        maximum_segment_iterations=self.maximum_segment_iterations,
        maximum_boundary_iterations=self.maximum_boundary_iterations,
        maximum_shooting_iterations=self.maximum_shooting_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return decision(
        MocChainTerminationReason.SOLVER_ERROR,
        f'ambient-closed physical next-cell solve raised: {error}',
        {'solver_error': type(error).__name__},
      )
    diagnostics['ambient_physical_field_result'] = result.as_report()
    if (
      result.converged
      and result.physical_closure_verified
      and result.state_sampling_available
      and result.upstream_coupling_verified
      and result.field is not None
    ):
      field = result.field
      if field.incoming_handoff != handoff:
        return decision(
          MocChainTerminationReason.STATE_NOT_CARRIED,
          'generated ambient-closed field did not retain the exact incoming handoff',
        )
      return MocPhysicalPostShockFieldContinuationSolve(
        field=field,
        end_x_m=end_x,
      )

    attachment = result.ambient_attachment
    shock = None if attachment is None else attachment.shock
    if shock is not None and shock.subsonic_terminal_required:
      terminal = shock.normal_shock_terminal
      if (
        not shock.terminal_model_verified
        or terminal is None
        or len(shock.upstream_states) != shock.sample_count
        or len(shock.upstream_pressure_Pa) != shock.sample_count
        or terminal.upstream_state is None
        or terminal.upstream_pressure_Pa is None
      ):
        return decision(
          MocChainTerminationReason.SOLVER_ERROR,
          'generated next-cell shock reached an incomplete normal-shock terminal; no physical endpoint was inferred',
          {'shock_status': shock.status.value},
        )
      return MocChainTerminationDecision(
        physical_termination=True,
        reason=MocChainTerminationReason.PHYSICAL_TERMINATION,
        message=(
          'generated next-cell shock reached a verified subsonic normal shock; '
          'the mixed-regime downstream field remains outside the supersonic '
          'MOC chain'
        ),
        diagnostics={
          **diagnostics,
          'termination_model': 'normal-shock-terminal',
          'shock_point_m': terminal.shock_point_m,
          'downstream_mach': terminal.downstream_mach,
          'downstream_pressure_Pa': terminal.downstream_pressure_Pa,
          'total_pressure_ratio': terminal.total_pressure_ratio,
          'upstream_sample_count': shock.sample_count,
          'shock_status': shock.status.value,
        },
      )
    if shock is not None and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE:
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'generated next-cell shock left the bounded upstream source; no extrapolation or endpoint was inferred',
        {
          'first_missing_sample_index': shock.failed_sample_index,
          'failed_point_m': shock.failed_point_m,
        },
      )
    if result.status is MocAmbientPhysicalFieldStatus.INVALID_INPUT:
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        f'generated ambient-closed next-cell solve rejected its inputs: {result.message}',
      )
    if result.status in (
      MocAmbientPhysicalFieldStatus.AMBIENT_ATTACHMENT_FAILURE,
      MocAmbientPhysicalFieldStatus.FIELD_FAILURE,
    ):
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'generated next-cell shock/ambient/centerline solve did not pass the physical closure gates',
      )
    return decision(
      MocChainTerminationReason.SOLVER_ERROR,
      'generated ambient-closed next-cell solve did not produce a complete field',
    )
  ####


@dataclass(frozen=True, slots=True)
class MocTerminalReflectionPatchAmbientClosureChainReference:
  """Configuration for the solver-owned reflected-patch chain lane.

  This reference deliberately has a smaller claim ceiling than the basic
  ambient-closed chain reference.  It derives each next upstream domain from
  the accepted field's terminal shock/ambient trace, reflects that trace to
  the centerline, and asks the ambient-closed physical-field solver to close
  the next cell.  It is therefore useful for a continued shock-cell-chain
  experiment while the canonical reflected free-boundary/remeshing problem
  and external validation remain open.
  """

  total_cell_count: int = 2
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  outer_downstream_flow_angle_lower_rad: float = -0.2
  outer_downstream_flow_angle_upper_rad: float = 0.2
  sample_count: int = 9
  branch: ShockBranch = ShockBranch.WEAK
  trace_position_tolerance_m: float = 1.0e-3
  trace_forward_tolerance_m: float = 1.0e-4
  seam_position_tolerance_m: float = 5.0e-3
  position_tolerance_m: float = 1.0e-9
  invariant_tolerance: float = 1.0e-10
  attachment_pressure_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  shock_angle_tolerance_rad: float = 1.0e-2
  maximum_segment_iterations: int = 24
  maximum_boundary_iterations: int = 16
  maximum_shooting_iterations: int = 40
  allow_zero_strength_attachment: bool = True
  polarity_aware: bool = True
  compression_amplitude_rad: float = 1.0e-2
  model: str = (
    'solver-generated-terminal-reflection-patch-ambient-closure-chain-reference'
  )

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    if not isinstance(self.allow_zero_strength_attachment, bool):
      raise TypeError('allow_zero_strength_attachment must be a bool')
    if not isinstance(self.polarity_aware, bool):
      raise TypeError('polarity_aware must be a bool')
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'outer_downstream_flow_angle_lower_rad',
      'outer_downstream_flow_angle_upper_rad',
      'trace_position_tolerance_m',
      'trace_forward_tolerance_m',
      'seam_position_tolerance_m',
      'position_tolerance_m',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      object.__setattr__(self, name, value)
    if (
      self.outer_downstream_flow_angle_lower_rad
      >= self.outer_downstream_flow_angle_upper_rad
    ):
      raise ValueError(
        'outer downstream flow-angle lower bound must be below its upper bound'
      )
    for name in (
      'trace_position_tolerance_m',
      'trace_forward_tolerance_m',
      'seam_position_tolerance_m',
      'position_tolerance_m',
      'invariant_tolerance',
      'attachment_pressure_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'shock_angle_tolerance_rad',
    ):
      if getattr(self, name) <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    amplitude = float(self.compression_amplitude_rad)
    if not isfinite(amplitude) or amplitude <= 0.0:
      raise ValueError(
        'compression_amplitude_rad must be finite and positive'
      )
    object.__setattr__(self, 'compression_amplitude_rad', amplitude)
    for name in (
      'maximum_segment_iterations',
      'maximum_boundary_iterations',
      'maximum_shooting_iterations',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'model', model)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': False,
      # The reference may exercise a locally accepted physical-field
      # continuation, but its reflected-domain/remeshing and external
      # validation gates are still open.  Keep the serialized claim ceiling
      # aligned with the chain and result contracts.
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'outer_downstream_flow_angle_bracket': (
        self.outer_downstream_flow_angle_lower_rad,
        self.outer_downstream_flow_angle_upper_rad,
      ),
      'sample_count': self.sample_count,
      'branch': self.branch.value,
      'trace_position_tolerance_m': self.trace_position_tolerance_m,
      'trace_forward_tolerance_m': self.trace_forward_tolerance_m,
      'seam_position_tolerance_m': self.seam_position_tolerance_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'attachment_pressure_tolerance': self.attachment_pressure_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'allow_zero_strength_attachment': self.allow_zero_strength_attachment,
      'polarity_aware': self.polarity_aware,
      'compression_amplitude_rad': self.compression_amplitude_rad,
      'downstream_condition_model': (
        'bounded-terminal-reflection-patch-plus-ambient-attachment-and-'
        'centerline-reflection'
        + (
          '-with-reflected-trace-compression-envelope'
          if self.polarity_aware else ''
        )
      ),
      'upstream_source_model': 'accepted-field-derived-terminal-reflection-patch',
      'claim_status': (
        'solver-generated-terminal-reflection-patch-ambient-closure-chain; '
        'canonical-reflected-free-boundary-and-external-validation-pending'
      ),
    }
  ####

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
    current_field: MocPhysicalPostShockFieldResult,
    *,
    end_x_m: float,
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'terminal-reflection-patch ambient-closure chain reference exhausted '
          f'its {self.total_cell_count}-cell research configuration'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_cell_index': next_cell_index,
          'termination_model': 'configured-cell-count',
        },
      )
    return solve_ambient_closed_post_shock_chain_cell_from_terminal_reflection_patch_ambient_closure_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      end_x_m=end_x_m,
      outer_downstream_flow_angle_lower_rad=(
        self.outer_downstream_flow_angle_lower_rad
      ),
      outer_downstream_flow_angle_upper_rad=(
        self.outer_downstream_flow_angle_upper_rad
      ),
      target_centerline_y_m=self.target_centerline_y_m,
      target_centerline_flow_angle_rad=self.target_centerline_flow_angle_rad,
      sample_count=self.sample_count,
      branch=self.branch,
      trace_position_tolerance_m=self.trace_position_tolerance_m,
      trace_forward_tolerance_m=self.trace_forward_tolerance_m,
      seam_position_tolerance_m=self.seam_position_tolerance_m,
      position_tolerance_m=self.position_tolerance_m,
      invariant_tolerance=self.invariant_tolerance,
      attachment_pressure_tolerance=self.attachment_pressure_tolerance,
      pressure_tolerance=self.pressure_tolerance,
      tangent_tolerance=self.tangent_tolerance,
      shock_angle_tolerance_rad=self.shock_angle_tolerance_rad,
      maximum_segment_iterations=self.maximum_segment_iterations,
      maximum_boundary_iterations=self.maximum_boundary_iterations,
      maximum_shooting_iterations=self.maximum_shooting_iterations,
      allow_zero_strength_attachment=self.allow_zero_strength_attachment,
      polarity_aware=self.polarity_aware,
      compression_amplitude_rad=self.compression_amplitude_rad,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedAmbientClosedPostShockChainMock:
  """Planner fixture for repeated bounded physical-field re-solves.

  Each configured candidate supplies only a next-shock curve, its requested
  downstream turns, an ambient-pressure boundary sample set, and an axial
  endpoint.  The real physical continuation solver samples the upstream
  state and pressure from the field accepted at the preceding step.  A
  candidate that leaves that finite field therefore produces a typed stop;
  it is never filled with a uniform state or extrapolated pressure.

  The fixture is intentionally prescribed-boundary evidence.  It exercises
  the multi-cell handoff and physical-field gates, but it is not a reflected
  free-boundary solver and cannot support a product claim.
  """

  candidates: tuple[MocAmbientClosedPostShockChainCandidate, ...] = ()
  branch: ShockBranch = ShockBranch.WEAK
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  shock_angle_tolerance_rad: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  model: str = 'prescribed-ambient-closed-post-shock-chain-mock'

  def __post_init__(self) -> None:
    try:
      candidates = tuple(self.candidates)
    except TypeError as error:
      raise TypeError(
        'candidates must be an iterable of '
        'MocAmbientClosedPostShockChainCandidate values'
      ) from error
    if any(
      not isinstance(candidate, MocAmbientClosedPostShockChainCandidate)
      for candidate in candidates
    ):
      raise TypeError(
        'candidates must contain '
        'MocAmbientClosedPostShockChainCandidate values'
      )
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    for name, value in (
      ('position_tolerance_m', self.position_tolerance_m),
      ('invariant_tolerance', self.invariant_tolerance),
      ('shock_angle_tolerance_rad', self.shock_angle_tolerance_rad),
      ('pressure_tolerance', self.pressure_tolerance),
      ('tangent_tolerance', self.tangent_tolerance),
    ):
      numeric_value = float(value)
      if not isfinite(numeric_value) or numeric_value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, numeric_value)
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'candidates', candidates)
    object.__setattr__(self, 'model', model)
  ####

  @property
  def total_cell_count_including_seed(self) -> int:
    """Return the number of accepted seed/candidate slots in the fixture."""

    return len(self.candidates) + 1
  ####

  def candidate_for_cell(
    self,
    next_cell_index: int,
  ) -> MocAmbientClosedPostShockChainCandidate | None:
    """Return the candidate for a one-based continued-cell index."""

    if (
      isinstance(next_cell_index, bool)
      or not isinstance(next_cell_index, int)
      or next_cell_index < 2
    ):
      raise ValueError('next_cell_index must be an integer of at least two')
    candidate_index = next_cell_index - 2
    if candidate_index >= len(self.candidates):
      return None
    return self.candidates[candidate_index]
  ####

  def as_report(self) -> dict[str, Any]:
    """Return fixture provenance and every explicit candidate schedule."""

    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': False,
      'claim_fidelity_ceiling': (
        MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
      ),
      'free_boundary_verified': False,
      'physical_chain_promotion_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count_including_seed,
      'candidate_count': len(self.candidates),
      'branch': self.branch.value,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'candidate_boundary_model': (
        'explicit-shock-curve-and-ambient-pressure-samples'
      ),
      'upstream_state_model': (
        'bounded-previous-ambient-closed-physical-field'
      ),
      'candidate_schedule': [
        {
          'next_cell_index': index + 2,
          **candidate.as_report(),
        }
        for index, candidate in enumerate(self.candidates)
      ],
      'claim_status': (
        'prescribed-ambient-closed-physical-field-chain-mock; '
        'canonical-reflected-free-boundary-and-external-validation-pending'
      ),
    }
  ####

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
    upstream_field: MocPhysicalPostShockFieldResult,
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    """Solve the configured candidate against the supplied bounded field."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if (
      isinstance(next_cell_index, bool)
      or not isinstance(next_cell_index, int)
      or next_cell_index != current.cell_index + 1
    ):
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    if not isinstance(upstream_field, MocPhysicalPostShockFieldResult):
      raise TypeError('upstream_field must be a MocPhysicalPostShockFieldResult')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    candidate = self.candidate_for_cell(next_cell_index)
    if candidate is None:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'prescribed ambient-closed physical-field chain mock exhausted '
          f'its configured {self.total_cell_count_including_seed}-cell fixture'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_cell_index': next_cell_index,
          'termination_model': 'configured-candidate-count',
        },
      )
    solved = solve_ambient_closed_post_shock_chain_cell_from_candidate_or_termination(
      current,
      next_cell_index,
      handoff,
      upstream_field,
      candidate,
      branch=self.branch,
      position_tolerance_m=self.position_tolerance_m,
      invariant_tolerance=self.invariant_tolerance,
      shock_angle_tolerance_rad=self.shock_angle_tolerance_rad,
      pressure_tolerance=self.pressure_tolerance,
      tangent_tolerance=self.tangent_tolerance,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return _with_chain_solver_context(
        solved,
        model=self.model,
        next_cell_index=next_cell_index,
        incoming_handoff=handoff,
      )
    return solved
  ####


def plan_prescribed_post_shock_chain_mock(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  mock: MocPrescribedPostShockChainMock | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the reusable planning-only prescribed post-shock chain fixture."""

  fixture = MocPrescribedPostShockChainMock() if mock is None else mock
  if not isinstance(fixture, MocPrescribedPostShockChainMock):
    raise TypeError('mock must be a MocPrescribedPostShockChainMock')
  planner = plan_post_shock_characteristic_chain(
    seed,
    fixture.solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
  )
  return replace(
    planner,
    diagnostics={
      'prescribed_chain_mock': fixture.as_report(),
    },
  )


def plan_solver_generated_post_shock_chain_reference(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocSolverGeneratedPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the reusable solver-generated, research-only chain reference."""

  fixture = (
    MocSolverGeneratedPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(fixture, MocSolverGeneratedPostShockChainReference):
    raise TypeError(
      'reference must be a MocSolverGeneratedPostShockChainReference'
    )
  planner = plan_post_shock_characteristic_chain(
    seed,
    fixture.solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  )
  return replace(
    planner,
    diagnostics={
      'solver_generated_chain_reference': fixture.as_report(),
    },
  )


def plan_field_coupled_post_shock_chain_reference(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocFieldCoupledPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the bounded prior-field-fed, research-only chain reference."""

  fixture = (
    MocFieldCoupledPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(fixture, MocFieldCoupledPostShockChainReference):
    raise TypeError(
      'reference must be a MocFieldCoupledPostShockChainReference'
    )
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-field-coupled-shock-chain-reference; '
      'canonical-reflected-domain-and-physical-downstream-boundary-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'field_coupled_chain_reference': fixture.as_report(),
      'upstream_field_replacement_policy': (
        'replace-only-after-complete-field-coupled-solve'
      ),
    },
  )
####


def _default_claim_status(kind: MocChainPlannerKind) -> str:
  return {
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK: (
      'deterministic-prescribed-next-shock-planner-mock; not-free-boundary-chain-evidence'
    ),
    MocChainPlannerKind.SOLVER_GENERATED_REFERENCE: (
      'solver-generated-chain-reference; physical-free-boundary-validation-pending'
    ),
    MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH: (
      'upstream-coupled-research-chain; external-validation-and-product-promotion-pending'
    ),
  }[kind]
####


def plan_moc_chain(
  seed: MocChainCell,
  solve_next: MocCellContinuationSolver,
  *,
  policy: MocChainContinuationPolicy | None = None,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Run the generic chain contract while recording every planned handoff."""

  steps: list[MocChainPlannerStep] = []

  def wrapped(current: MocChainCell, next_cell_index: int):
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      current.continuation_boundary,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_moc_cell_chain(seed, wrapped, policy)
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_terminal_reflection_patch_chain(
  seed: MocChainCell,
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 2.0e-4,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one terminal-reflection handoff through the generic chain audit.

  A terminal reflection patch is a finite upstream domain for one next-shock
  solve, not a reusable downstream field for an arbitrary number of later
  cells.  This wrapper therefore allows the adapter to be invoked once and
  records any returned cell or typed termination through ``plan_moc_chain``.
  A second callback invocation receives an explicit non-physical solver stop
  rather than reusing the terminal patch outside its solved domain.
  """

  if not isinstance(patch, MocTerminalReflectionPatchResult):
    raise TypeError('patch must be a MocTerminalReflectionPatchResult')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'terminal reflection patch planner completed its one-step domain; '
          'a later cell requires a new upstream field and solver adapter'
        ),
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      patch,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  return plan_moc_chain(
    seed,
    solve_next,
    policy=policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'terminal-reflection-patch-planner-handoff; '
      'one-step-domain; mixed-regime-or-new-field-continuation-pending'
    ),
  )


def plan_post_shock_zone_chain(
  seed: MocChainCell,
  post_shock_zone: MocPostShockCharacteristicZoneResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one next shock against a bounded open post-shock zone.

  The open zone is a finite solver interface, not a resolved chain cell.  It
  can therefore be consumed for one next-shock attempt only.  A completely
  covered shock plus closed downstream field is returned as a resolved
  research cell; a zone boundary, subsonic terminal, or solver failure is
  retained as the typed planner stop.  The planner never reuses the original
  open zone for a later cell and never changes its research-only claim.
  """

  if not isinstance(post_shock_zone, MocPostShockCharacteristicZoneResult):
    raise TypeError(
      'post_shock_zone must be a MocPostShockCharacteristicZoneResult'
    )
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'open post-shock zone planner completed its one-step upstream '
          'domain; a later cell requires a newly solved bounded field'
        ),
        diagnostics={
          'termination_model': 'open-post-shock-zone-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_zone_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      post_shock_zone,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-open-post-shock-zone-next-shock-planner; '
      'one-step-domain-and-physical-downstream-closure-pending'
    ),
  )


def plan_caustic_family_band_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one caustic-band-to-shock handoff through the chain audit.

  The caustic band is a finite upstream field for one next-shock solve.  Its
  current solver result ends at an open mixed-regime boundary, so a successful
  attempt produces an explicit non-physical ``OPEN_PHYSICAL_CLOSURE`` stop.
  The planner never reuses that band for a second cell and never promotes the
  open terminal field as a resolved chain cell.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic-family band planner completed its one-step upstream '
          'domain; a later cell requires a new family or post-shock field'
        ),
        diagnostics={
          'termination_model': 'caustic-family-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      band,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-family-band-next-shock-planner; '
      'open-mixed-regime-closure-and-external-validation-pending'
    ),
  )
####


def plan_caustic_origin_envelope_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  position_tolerance_m: float = 1.0e-10,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Audit a caustic-origin reachability attempt at a chain boundary.

  The weak attached forward envelope is a pre-shock remeshing diagnostic.  It
  can return a typed ``CHARACTERISTIC_CAUSTIC`` stop when the finite family
  band ends before the centerline, but it can never append an envelope as a
  resolved chain cell.  The planner permits one finite-domain attempt and
  records the exact prior handoff before invoking the probe.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic-origin envelope planner completed its one-step remesh '
          'diagnostic; a later cell requires a physically solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-origin-envelope-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    envelope = trace_caustic_family_band_forward_envelope(
      band,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      position_tolerance_m=position_tolerance_m,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if (
      envelope.status
      is MocCausticFamilyBandEnvelopeStatus.CENTERLINE_UNREACHABLE
    ):
      return envelope.as_chain_termination_decision()
    if envelope.status is MocCausticFamilyBandEnvelopeStatus.INVALID_INPUT:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=envelope.message,
        diagnostics={
          'termination_model': 'caustic-origin-envelope-invalid-input',
          'envelope_status': envelope.status.value,
        },
      )
    if envelope.converged:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'caustic-origin forward envelope reached the centerline, but no '
          'shock curve, downstream field, or mixed-regime closure was solved'
        ),
        diagnostics={
          'termination_model': 'caustic-origin-envelope-reachability-only',
          'envelope_status': envelope.status.value,
          'envelope_sample_count': envelope.sample_count,
        },
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=envelope.message,
      diagnostics={
        'termination_model': 'caustic-origin-envelope-probe-failure',
        'envelope_status': envelope.status.value,
      },
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-origin-forward-envelope-planner; physical-remesh-and-'
      'shock-closure-pending'
    ),
  )
####


def plan_caustic_family_band_invariant_chain(
  seed: MocChainCell,
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan an invariant-conditioned caustic shock-chain continuation.

  The planner records the exact prior handoff and permits at most the finite
  family-band domain to be consumed.  Its provenance is always
  ``UPSTREAM_COUPLED_RESEARCH`` and its production claim remains disabled,
  even if a future remeshed band allows the local field to converge.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'invariant-conditioned caustic-band planner consumed its one-step '
          'upstream domain; a later cell requires a new upstream field'
        ),
        diagnostics={
          'termination_model': 'invariant-caustic-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      band,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_at=downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'invariant-conditioned-caustic-band-shock-planner; '
      'one-sided-upstream-domain-and-physical-remesh-pending'
    ),
  )


def plan_caustic_upstream_continuation(
  old_family: MocSourceCharacteristicStripResult,
  seed: MocSourceStripCausticShockSeedResult,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  *,
  anchor_edge_index: int | None = None,
  sample_count: int = 6,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
  side_at: Callable[[tuple[float, float]], MocCausticBridgeSide] | None = None,
  claim_status: str | None = None,
) -> MocCausticUpstreamContinuationPlannerResult:
  """Plan a branch-explicit upstream continuation at a caustic.

  The planner always audits both one-sided restart candidates.  Supplying an
  ``anchor_edge_index`` then runs the selected branch through the exact event
  seam; omitting it leaves the result at ``BRANCH_SELECTION_REQUIRED``.  In
  either case the returned termination is non-physical and no chain cell is
  appended.  A later shock-cell planner may consume the selected bounded
  bridge only after a separate, explicit solver contract accepts it.
  """

  if anchor_edge_index is None and side_at is not None:
    raise ValueError(
      'side_at requires an explicit anchor_edge_index'
    )
  branch_audit = solve_caustic_upstream_continuation(
    old_family,
    seed,
    total_pressure_Pa,
    ambient_pressure_Pa,
    sample_count=sample_count,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    maximum_iterations=maximum_iterations,
  )
  continuation = branch_audit
  if anchor_edge_index is not None:
    continuation = solve_caustic_upstream_continuation(
      old_family,
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=sample_count,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
      side_at=side_at,
    )

  termination = continuation.as_chain_termination_decision()
  return MocCausticUpstreamContinuationPlannerResult(
    branch_audit=branch_audit,
    continuation=continuation,
    termination=termination,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-owned-caustic-upstream-continuation-planner; '
      'bounded-bridge-only; shock-remesh-and-physical-closure-pending'
      if claim_status is None
      else claim_status
    ),
    diagnostics={
      'continuation_model': 'branch-explicit-caustic-upstream-continuation',
      'branch_audit_status': branch_audit.status.value,
      'branch_candidate_count': len(branch_audit.restart_results),
      'branch_audit_verified': (
        branch_audit.status is (
          MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED
        )
        and len(branch_audit.restart_results) == 2
        and all(
          restart.converged
          and restart.caustic_handoff_verified
          and restart.family_band is not None
          and restart.family_band.converged
          for restart in branch_audit.restart_results
        )
      ),
      'selected_anchor_edge_index': continuation.selected_anchor_edge_index,
      'continuation_status': continuation.status.value,
      'seam_verified': continuation.seam_verified,
      'state_sampling_available': continuation.state_sampling_available,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'chain_cell_appended': False,
    },
  )


def plan_caustic_upstream_bridge_chain(
  seed: MocChainCell,
  bridge: MocCausticUpstreamBridge,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a one-step shock attempt across an explicit caustic bridge.

  The bridge is a finite upstream sampling domain, not a reusable chain
  field.  This planner records the exact incoming handoff, maps a bounded
  domain gap or ambiguous overlap to a typed non-physical stop, and never
  promotes the bridge's open physical seam into a resolved cell.
  """

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  try:
    requested_end_x = float(end_x_m)
  except (TypeError, ValueError) as error:
    raise ValueError('end_x_m must be finite and numeric') from error
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic upstream bridge planner consumed its one-step bounded '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-upstream-bridge-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_from_caustic_upstream_bridge(
      bridge,
      start_point_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      incoming_handoff=current.continuation_boundary,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    diagnostics = {
      'termination_model': 'caustic-upstream-bridge',
      'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
      'next_cell_index': next_cell_index,
      'requested_end_x_m': requested_end_x,
      'bridge_status': solved.coupling.status.value,
      'bridge_sampled_count': solved.coupling.sampled_count,
      'bridge_first_missing_sample_index': solved.coupling.first_missing_sample_index,
      'bridge_first_missing_point_m': solved.coupling.first_missing_point_m,
      'bridge_first_ambiguous_sample_index': solved.coupling.first_ambiguous_sample_index,
      'upstream_coupling_verified': solved.upstream_coupling_verified,
      'physical_closure_verified': solved.physical_closure_verified,
      'bridge_report': solved.coupling.as_report(),
      'shock_status': solved.shock.status.value,
    }
    if solved.coupling.status is MocCausticBridgeStatus.AMBIGUOUS_OVERLAP:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.CHARACTERISTIC_CAUSTIC,
        message=(
          'caustic bridge encountered overlapping one-sided fields without '
          'an explicit branch selection; no state was averaged'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status in (
      MocCausticBridgeStatus.DOMAIN_GAP,
      MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP,
      MocCausticBridgeStatus.FIELD_INPUT_FAILURE,
    ):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'caustic upstream bridge did not cover the next-shock path; no '
          'extrapolation or physical endpoint was inferred'
        ),
        diagnostics=diagnostics,
      )
    if not solved.upstream_coupling_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=(
          'caustic bridge shock solve did not retain a complete bounded '
          'upstream handoff; no next cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    if solved.shock.field is not None:
      expected_states = tuple(sample.state for sample in current.continuation_boundary)
      expected_pressures = tuple(
        sample.total_pressure_Pa for sample in current.continuation_boundary
      )
      if (
        solved.shock.field.incoming_handoff_states != expected_states
        or solved.shock.field.incoming_handoff_total_pressure_Pa != expected_pressures
      ):
        diagnostics['upstream_coupling_verified'] = False
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.STATE_NOT_CARRIED,
          message=(
            'caustic bridge shock field did not retain the exact incoming '
            'chain handoff'
          ),
          diagnostics=diagnostics,
        )
    if solved.shock.converged or solved.shock.terminal_model_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'caustic bridge supplied a bounded shock attempt, but the physical '
          'old-family/new-family seam and downstream cell closure remain '
          'unresolved; no cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'caustic bridge shock solve did not produce a complete next cell; no '
        'physical endpoint was inferred'
      ),
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-upstream-bridge-planner; physical-remesh-and-downstream-'
      'closure-pending'
    ),
  )


def plan_caustic_upstream_bridge_invariant_chain(
  seed: MocChainCell,
  bridge: MocCausticUpstreamBridge,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan an invariant-conditioned one-step caustic bridge shock attempt."""

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  try:
    requested_end_x = float(end_x_m)
  except (TypeError, ValueError) as error:
    raise ValueError('end_x_m must be finite and numeric') from error
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'invariant caustic bridge planner consumed its one-step bounded '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'invariant-caustic-upstream-bridge-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary(
      bridge,
      start_point_m,
      downstream_invariant_family,
      downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=current.continuation_boundary,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    diagnostics = {
      'termination_model': 'invariant-caustic-upstream-bridge',
      'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
      'next_cell_index': next_cell_index,
      'requested_end_x_m': requested_end_x,
      'invariant_family': downstream_invariant_family.value,
      'bridge_status': solved.coupling.status.value,
      'bridge_sampled_count': solved.coupling.sampled_count,
      'bridge_first_missing_sample_index': solved.coupling.first_missing_sample_index,
      'bridge_first_missing_point_m': solved.coupling.first_missing_point_m,
      'bridge_first_ambiguous_sample_index': solved.coupling.first_ambiguous_sample_index,
      'upstream_coupling_verified': solved.upstream_coupling_verified,
      'physical_closure_verified': solved.physical_closure_verified,
      'bridge_report': solved.coupling.as_report(),
      'shock_status': solved.shock.status.value,
    }
    if solved.coupling.status is MocCausticBridgeStatus.AMBIGUOUS_OVERLAP:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.CHARACTERISTIC_CAUSTIC,
        message=(
          'invariant caustic bridge encountered overlapping one-sided fields '
          'without explicit branch selection; no state was averaged'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status in (
      MocCausticBridgeStatus.DOMAIN_GAP,
      MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP,
      MocCausticBridgeStatus.FIELD_INPUT_FAILURE,
    ):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'invariant caustic bridge did not cover the next-shock path; no '
          'extrapolation or physical endpoint was inferred'
        ),
        diagnostics=diagnostics,
      )
    if solved.coupling.status is MocCausticBridgeStatus.PATH_GEOMETRY_FAILURE:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message='invariant caustic bridge rejected the shock-path geometry',
        diagnostics=diagnostics,
      )
    if not solved.upstream_coupling_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=(
          'invariant caustic bridge shock solve did not retain a complete '
          'upstream handoff; no next cell was promoted'
        ),
        diagnostics=diagnostics,
      )
    if solved.shock.field is not None:
      expected_states = tuple(sample.state for sample in current.continuation_boundary)
      expected_pressures = tuple(
        sample.total_pressure_Pa for sample in current.continuation_boundary
      )
      if (
        solved.shock.field.incoming_handoff_states != expected_states
        or solved.shock.field.incoming_handoff_total_pressure_Pa != expected_pressures
      ):
        diagnostics['upstream_coupling_verified'] = False
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.STATE_NOT_CARRIED,
          message='invariant caustic bridge shock field did not retain the exact incoming handoff',
          diagnostics=diagnostics,
        )
    if solved.shock.converged or solved.shock.terminal_model_verified:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          'invariant caustic bridge supplied a bounded shock attempt, but the '
          'physical branch seam and downstream cell closure remain unresolved'
        ),
        diagnostics=diagnostics,
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'invariant caustic bridge shock solve did not produce a complete next '
        'cell; no physical endpoint was inferred'
      ),
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'invariant-caustic-upstream-bridge-planner; physical-remesh-and-'
      'downstream-closure-pending'
    ),
  )


def plan_caustic_shock_remesh_chain(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
  _upstream_bridge: MocCausticUpstreamBridge | None = None,
) -> MocChainPlannerResult:
  """Plan one solver-backed caustic shock/new-family remesh attempt.

  The request identifies the exact one-sided caustic event and local shock
  compatibility state.  The current chain cell supplies the exact carried
  perimeter to the remesher.  A converged remesh is intentionally returned as
  an ``OPEN_PHYSICAL_CLOSURE`` stop: it produces a bounded shock and new
  characteristic field, but ambient/terminal closure for the new physical
  cell remains a separate first-cell gate.  The planner therefore never
  appends a remesh result as a chain cell.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    raise TypeError('request must be a MocCausticShockRemeshRequest')
  if not callable(upstream_state_at):
    raise TypeError('upstream_state_at must be callable')
  if not callable(upstream_pressure_at):
    raise TypeError('upstream_pressure_at must be callable')
  if downstream_invariant_at is not None and not callable(downstream_invariant_at):
    raise TypeError('downstream_invariant_at must be callable when supplied')
  if _upstream_bridge is not None and not isinstance(
    _upstream_bridge,
    MocCausticUpstreamBridge,
  ):
    raise TypeError('_upstream_bridge must be a MocCausticUpstreamBridge when supplied')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')

  attempted = False

  def remesh_decision(
    result: MocCausticShockRemeshResult,
    next_cell_index: int,
  ) -> MocChainTerminationDecision:
    decision = result.as_chain_termination_decision()
    diagnostics = dict(decision.diagnostics)
    diagnostics.update({
      'planner_model': 'caustic-shock-remesh-one-step-domain',
      'next_cell_index': next_cell_index,
      'remesh_report': result.as_report(),
    })
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=decision.reason,
      message=decision.message,
      diagnostics=diagnostics,
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic shock remesh planner completed its one-step domain; a '
          'later cell requires a newly closed physical upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-shock-remesh-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    event_x = request.event_point_m[0]
    if event_x < current.end_x_m - float(position_tolerance_m):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'caustic remesh event lies upstream of the current chain cell '
          'boundary; the planner will not back-extrapolate the handoff'
        ),
        diagnostics={
          'termination_model': 'caustic-shock-remesh-one-step-domain',
          'event_point_m': request.event_point_m,
          'current_end_x_m': current.end_x_m,
          'next_cell_index': next_cell_index,
        },
      )
    if _upstream_bridge is None:
      result = solve_caustic_shock_remesh(
        request,
        upstream_state_at,
        upstream_pressure_at,
        current.continuation_boundary,
        downstream_invariant_at=downstream_invariant_at,
        target_centerline_y_m=target_centerline_y_m,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_downstream_angle_rad=maximum_downstream_angle_rad,
        maximum_invariant_scan_samples=maximum_invariant_scan_samples,
        maximum_invariant_iterations=maximum_invariant_iterations,
      )
    else:
      result = solve_caustic_shock_remesh_from_upstream_bridge(
        request,
        _upstream_bridge,
        current.continuation_boundary,
        downstream_invariant_at=downstream_invariant_at,
        target_centerline_y_m=target_centerline_y_m,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_downstream_angle_rad=maximum_downstream_angle_rad,
        maximum_invariant_scan_samples=maximum_invariant_scan_samples,
        maximum_invariant_iterations=maximum_invariant_iterations,
      )
    return remesh_decision(result, next_cell_index)

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  planner = plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-shock-remesh-planner; solver-backed shock/new-family field '
      'with physical-first-cell-closure-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'caustic_shock_remesh_request': request.as_report(),
      'one_step_domain': True,
      'physical_closure_pending': True,
      'upstream_field_model': (
        'bounded-old-family-restarted-family-bridge'
        if _upstream_bridge is not None
        else 'callback-owned-upstream-field'
      ),
    },
  )


def plan_caustic_upstream_remesh_shock_chain(
  seed: MocPostShockCharacteristicFieldResult,
  remesh: MocCausticUpstreamRemeshResult,
  *,
  start_point_m: tuple[float, float],
  start_x_m: float,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one next-shock attempt from a caustic-conditioned Cauchy field.

  The remesh supplies one finite upstream characteristic domain.  A successful
  shock/field solve may append one research cell; the same remesh is never
  reused for another cell.  This keeps the planner mock and the physical
  upstream-remesh lane separate while making the exact chain boundary
  observable.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(remesh, MocCausticUpstreamRemeshResult):
    raise TypeError('remesh must be a MocCausticUpstreamRemeshResult')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if downstream_flow_angle_at is not None and not callable(
    downstream_flow_angle_at
  ):
    raise TypeError('downstream_flow_angle_at must be callable when supplied')
  if downstream_flow_angle_rad is not None and not isfinite(
    float(downstream_flow_angle_rad)
  ):
    raise ValueError('downstream_flow_angle_rad must be finite when supplied')
  if not isinstance(branch, ShockBranch):
    raise TypeError('branch must be a ShockBranch')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if len(start_point_m) != 2 or not all(
    isfinite(float(value)) for value in start_point_m
  ):
    raise ValueError('start_point_m must contain two finite coordinates')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    raise ValueError('sample_count must be an integer of at least three')
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    raise ValueError('maximum_segment_iterations must be a positive integer')

  source_strip = (
    remesh.strip
    if remesh.state_sampling_available
    and remesh.strip is not None
    and remesh.strip.converged
    else None
  )
  initial_decision = (
    None
    if source_strip is not None
    else remesh.as_chain_termination_decision()
  )
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'caustic upstream Cauchy remesh planner consumed its one-step '
          'source domain; a later cell requires a newly solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-upstream-remesh-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    if initial_decision is not None:
      decision = initial_decision
      diagnostics = dict(decision.diagnostics)
      diagnostics.update({
        'planner_model': 'caustic-upstream-remesh-one-step-domain',
        'next_cell_index': next_cell_index,
        'remesh_report': remesh.as_report(),
      })
      return replace(decision, diagnostics=diagnostics)
    assert source_strip is not None
    return solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      start_point_m=start_point_m,
      end_x_m=current.end_x_m + float(end_x_m) - float(start_x_m),
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-upstream-cauchy-remesh-shock-chain; one-step-bounded-domain; '
      'physical-caustic-and-ambient-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_upstream_remesh': remesh.as_report(),
    'source_strip_chain_model': 'caustic-upstream-cauchy-remesh-one-step',
    'one_step_domain': True,
    'source_strip_reuse_policy': (
      'never-reuse-after-one-next-cell-attempt'
    ),
    'physical_closure_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)


def plan_caustic_upstream_remesh_shock_chain_sequence(
  seed: MocPostShockCharacteristicFieldResult,
  remesh: MocCausticUpstreamRemeshResult,
  remesh_at: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocCausticUpstreamRemeshResult | MocChainTerminationDecision | None,
  ],
  *,
  start_point_at: Callable[
    [MocChainCell, int, MocCausticUpstreamRemeshResult],
    tuple[float, float],
  ],
  start_x_m: float,
  end_x_m: float,
  end_x_at: Callable[
    [MocChainCell, int, MocCausticUpstreamRemeshResult],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan continued cells with a fresh caustic remesh for every shock.

  ``remesh`` supplies the first bounded upstream Cauchy domain.  After a
  successful cell, ``remesh_at`` must solve a new domain from the exact
  outgoing handoff before the next shock is attempted.  Neither a prior
  remesh result nor its source strip may be reused, and a missing or invalid
  remesh becomes a typed upstream-field boundary.  This is the multi-cell
  counterpart to :func:`plan_caustic_upstream_remesh_shock_chain`; it remains
  a research planner because the canonical outer trace, mixed-regime closure,
  and external validation are still separate gates.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(remesh, MocCausticUpstreamRemeshResult):
    raise TypeError('remesh must be a MocCausticUpstreamRemeshResult')
  if not callable(remesh_at):
    raise TypeError('remesh_at must be callable')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if downstream_flow_angle_at is not None and not callable(
    downstream_flow_angle_at
  ):
    raise TypeError('downstream_flow_angle_at must be callable when supplied')
  if downstream_flow_angle_rad is not None and not isfinite(
    float(downstream_flow_angle_rad)
  ):
    raise ValueError('downstream_flow_angle_rad must be finite when supplied')
  if not isinstance(branch, ShockBranch):
    raise TypeError('branch must be a ShockBranch')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if not isfinite(float(target_centerline_y_m)):
    raise ValueError('target_centerline_y_m must be finite')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    raise ValueError('sample_count must be an integer of at least three')
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    raise ValueError('maximum_segment_iterations must be a positive integer')

  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  source_strip = (
    remesh.strip
    if remesh.state_sampling_available
    and remesh.strip is not None
    and remesh.strip.converged
    else None
  )
  initial_decision = (
    None
    if source_strip is not None
    else remesh.as_chain_termination_decision()
  )

  remesh_history: list[MocCausticUpstreamRemeshResult] = [remesh]
  used_remesh_ids = {id(remesh)}
  used_strip_ids = (
    {id(remesh.strip)} if remesh.strip is not None else set()
  )
  initial_fingerprint = _caustic_upstream_remesh_fingerprint(remesh)
  used_fingerprints = (
    {initial_fingerprint} if initial_fingerprint is not None else set()
  )
  remesh_attempts: list[dict[str, Any]] = [{
    'current_cell_index': 1,
    'next_cell_index': 2,
    'role': 'initial-caustic-upstream-remesh',
    'remesh': remesh.as_report(),
    'fresh_remesh': True,
    'fresh_strip': remesh.strip is not None,
    'remesh_fingerprint': initial_fingerprint,
  }]

  def boundary_stop(
    candidate: MocCausticUpstreamRemeshResult,
    next_cell_index: int,
    *,
    message: str | None = None,
    policy_label: str = 'fresh-bounded-caustic-remesh-required-per-cell',
    allow_remesh_decision: bool = True,
    reason_override: MocChainTerminationReason | None = None,
    extra_diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    if allow_remesh_decision and reason_override is None:
      decision = candidate.as_chain_termination_decision()
      diagnostics = dict(decision.diagnostics)
      diagnostics.update({
        'next_cell_index': next_cell_index,
        'remesh_reuse_policy': policy_label,
        'caustic_upstream_remesh': candidate.as_report(),
      })
      return replace(decision, diagnostics=diagnostics)
    diagnostics: dict[str, Any] = {
      'termination_model': 'caustic-upstream-remesh-sequence',
      'next_cell_index': next_cell_index,
      'remesh_reuse_policy': policy_label,
      'caustic_upstream_remesh': candidate.as_report(),
    }
    if extra_diagnostics is not None:
      diagnostics.update(extra_diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
        if reason_override is None
        else reason_override
      ),
      message=(
        message
        or 'caustic remesh provider did not provide a fresh bounded upstream field'
      ),
      diagnostics=diagnostics,
    )

  def provider_failure(
    next_cell_index: int,
    message: str,
    *,
    reason: MocChainTerminationReason = MocChainTerminationReason.SOLVER_ERROR,
  ) -> MocChainTerminationDecision:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'termination_model': 'caustic-upstream-remesh-sequence',
        'next_cell_index': next_cell_index,
        'remesh_reuse_policy': (
          'fresh-bounded-caustic-remesh-required-per-cell'
        ),
      },
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    using_initial_remesh = next_cell_index == 2
    if next_cell_index == 2:
      if initial_decision is not None:
        return initial_decision
      next_remesh: (
        MocCausticUpstreamRemeshResult
        | MocChainTerminationDecision
        | None
      ) = remesh
    else:
      try:
        next_remesh = remesh_at(current, next_cell_index, incoming_handoff)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        remesh_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'remesh-provider',
          'provider_error': type(error).__name__,
          'fresh_remesh': False,
          'fresh_strip': False,
        })
        return provider_failure(
          next_cell_index,
          f'caustic upstream remesh provider failed: {error}',
        )
    if next_remesh is None:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'remesh-provider',
        'provider_result': None,
        'fresh_remesh': False,
        'fresh_strip': False,
      })
      return provider_failure(
        next_cell_index,
        'caustic upstream remesh provider returned no bounded field',
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      )
    if isinstance(next_remesh, MocChainTerminationDecision):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'remesh-provider',
        'provider_decision': next_remesh.as_report(),
        'fresh_remesh': False,
        'fresh_strip': False,
      })
      if next_remesh.physical_termination:
        return provider_failure(
          next_cell_index,
          'caustic remesh provider cannot declare physical plume termination '
          'from an upstream domain boundary',
          reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        )
      return next_remesh
    if not isinstance(next_remesh, MocCausticUpstreamRemeshResult):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'remesh-provider',
        'provider_result_type': type(next_remesh).__name__,
        'fresh_remesh': False,
        'fresh_strip': False,
      })
      return provider_failure(
        next_cell_index,
        'caustic remesh provider must return a MocCausticUpstreamRemeshResult, '
        'MocChainTerminationDecision, or None',
        reason=MocChainTerminationReason.INVALID_INPUT,
      )

    incoming_handoff_verified = bool(
      next_remesh.request is not None
      and next_remesh.request.incoming_handoff == incoming_handoff
    )
    if not using_initial_remesh and not incoming_handoff_verified:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'remesh-provider-handoff-seam',
        'incoming_handoff_sample_count': len(incoming_handoff),
        'remesh_request_incoming_handoff_sample_count': (
          None
          if next_remesh.request is None
          else len(next_remesh.request.incoming_handoff)
        ),
        'incoming_handoff_verified': False,
        'fresh_remesh': False,
        'fresh_strip': False,
      })
      return boundary_stop(
        next_remesh,
        next_cell_index,
        message=(
          'caustic remesh provider did not record the exact prior chain '
          'handoff in its request; a later upstream domain cannot be '
          'detached from the cell it continues'
        ),
        policy_label='require-exact-incoming-handoff-provenance',
        allow_remesh_decision=False,
        reason_override=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        extra_diagnostics={
          'incoming_handoff_sample_count': len(incoming_handoff),
          'remesh_request_incoming_handoff_sample_count': (
            None
            if next_remesh.request is None
            else len(next_remesh.request.incoming_handoff)
          ),
          'incoming_handoff_verified': False,
        },
      )

    fingerprint = _caustic_upstream_remesh_fingerprint(next_remesh)
    strip_reused = (
      next_remesh.strip is not None
      and (
        id(next_remesh.strip) in used_strip_ids
        or fingerprint is None
        or fingerprint in used_fingerprints
      )
    )
    remesh_reused = id(next_remesh) in used_remesh_ids or strip_reused
    if not using_initial_remesh:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'remesh-provider',
        'remesh': next_remesh.as_report(),
        'fresh_remesh': not remesh_reused,
        'fresh_strip': next_remesh.strip is not None and not strip_reused,
        'remesh_fingerprint': fingerprint,
        'incoming_handoff_sample_count': len(incoming_handoff),
        'incoming_handoff_verified': incoming_handoff_verified,
      })
    if remesh_reused and not using_initial_remesh:
      return boundary_stop(
        next_remesh,
        next_cell_index,
        message=(
          'caustic remesh provider reused a prior remesh or source strip; '
          'a fresh bounded upstream domain is required for each continued '
          'shock cell'
        ),
        policy_label='reject-reused-caustic-remesh-or-source-strip',
        allow_remesh_decision=False,
      )
    if not using_initial_remesh:
      remesh_history.append(next_remesh)
      used_remesh_ids.add(id(next_remesh))
      if next_remesh.strip is not None:
        used_strip_ids.add(id(next_remesh.strip))
        if fingerprint is not None:
          used_fingerprints.add(fingerprint)

    if (
      next_remesh.request is not None
      and next_remesh.request.event_point_m[0]
      < current.end_x_m - float(position_tolerance_m)
    ):
      return boundary_stop(
        next_remesh,
        next_cell_index,
        message=(
          'caustic upstream remesh event lies upstream of the current cell '
          'interface; no backtracking or extrapolation was performed'
        ),
        reason_override=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      )
    if not next_remesh.state_sampling_available or next_remesh.strip is None:
      return boundary_stop(next_remesh, next_cell_index)

    try:
      start_point = start_point_at(current, next_cell_index, next_remesh)
      if len(start_point) != 2 or not all(
        isfinite(float(value)) for value in start_point
      ):
        raise ValueError('start_point_at must return two finite coordinates')
      next_end_x = (
        end_x_at(current, next_cell_index, next_remesh)
        if end_x_at is not None
        else current.end_x_m + cell_axial_length_m
      )
      if not isfinite(float(next_end_x)) or next_end_x <= current.end_x_m:
        raise ValueError(
          'continued remesh cell endpoint must be finite and downstream of '
          'the current cell interface'
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return provider_failure(
        next_cell_index,
        f'caustic remesh chain geometry provider failed: {error}',
        reason=MocChainTerminationReason.INVALID_INPUT,
      )
    return solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      next_remesh.strip,
      start_point_m=(float(start_point[0]), float(start_point[1])),
      end_x_m=float(next_end_x),
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-upstream-cauchy-remesh-shock-chain-sequence; '
      'fresh-bounded-domain-per-cell; physical-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_upstream_remesh_chain_model': (
      'fresh-bounded-caustic-upstream-remesh-per-cell'
    ),
    'caustic_upstream_remesh': remesh.as_report(),
    'one_step_domain': False,
    'upstream_remesh_reuse_policy': (
      'fresh-bounded-caustic-remesh-required-per-cell'
    ),
    'upstream_remesh_domain_count': len(remesh_history),
    'upstream_remesh_domain_attempt_count': len(remesh_attempts),
    'upstream_remesh_domain_attempts': remesh_attempts,
    'physical_closure_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)


def plan_caustic_simple_wave_terminal_chain(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  *,
  upstream_invariant_family: CharacteristicFamily = CharacteristicFamily.MINUS,
  target_centerline_y_m: float = 0.0,
  upstream_centerline_flow_angle_rad: float = 0.0,
  downstream_centerline_flow_angle_rad: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  maximum_x_m: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one solver-owned simple-wave caustic terminal attempt.

  The simple-wave lane is intentionally one-step.  It gives the planner a
  real attached-shock prefix, open post-shock characteristic zone, and typed
  normal-shock terminal to audit, but it never appends the open result as a
  resolved chain cell.  A later supersonic cell needs a physically closed
  mixed-regime handoff and a newly solved upstream field.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    raise TypeError('request must be a MocCausticShockRemeshRequest')
  if downstream_flow_angle_at is not None and not callable(downstream_flow_angle_at):
    raise TypeError('downstream_flow_angle_at must be callable when supplied')
  if not isinstance(branch, ShockBranch):
    raise TypeError('branch must be a ShockBranch')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 5:
    raise ValueError('sample_count must be an integer of at least five')

  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'simple-wave caustic terminal planner completed its one-step '
          'domain; a later cell requires a new solved upstream field'
        ),
        diagnostics={
          'termination_model': 'caustic-simple-wave-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    event_x = request.event_point_m[0]
    if event_x < current.end_x_m - float(position_tolerance_m):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'simple-wave caustic event lies upstream of the current chain cell '
          'boundary; the planner will not back-extrapolate the handoff'
        ),
        diagnostics={
          'termination_model': 'caustic-simple-wave-one-step-domain',
          'event_point_m': request.event_point_m,
          'current_end_x_m': current.end_x_m,
          'next_cell_index': next_cell_index,
        },
      )
    result = solve_caustic_simple_wave_terminal_remesh(
      request,
      current.continuation_boundary,
      upstream_invariant_family=upstream_invariant_family,
      target_centerline_y_m=target_centerline_y_m,
      upstream_centerline_flow_angle_rad=upstream_centerline_flow_angle_rad,
      downstream_centerline_flow_angle_rad=downstream_centerline_flow_angle_rad,
      downstream_flow_angle_at=downstream_flow_angle_at,
      maximum_x_m=maximum_x_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    decision = result.as_chain_termination_decision()
    diagnostics = dict(decision.diagnostics)
    diagnostics.update({
      'planner_model': 'caustic-simple-wave-terminal-one-step-domain',
      'next_cell_index': next_cell_index,
      'simple_wave_terminal_report': result.as_report(),
      'upstream_field_model': 'solver-owned-constant-invariant-simple-wave-trace',
      'physical_closure_pending': True,
    })
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=decision.reason,
      message=decision.message,
      diagnostics=diagnostics,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  planner = plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-simple-wave-terminal planner; solver-owned simple-wave trace '
      'with open mixed-regime closure and physical-remesh validation pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'caustic_shock_remesh_request': request.as_report(),
      'one_step_domain': True,
      'physical_closure_pending': True,
      'upstream_field_model': 'solver-owned-constant-invariant-simple-wave-trace',
      'simple_wave_invariant_family': upstream_invariant_family.value,
      'simple_wave_target_centerline_y_m': target_centerline_y_m,
    },
  )


def plan_caustic_shock_remesh_chain_from_upstream_bridge(
  seed: MocChainCell,
  request: MocCausticShockRemeshRequest,
  bridge: MocCausticUpstreamBridge,
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a caustic remesh using the strict bounded upstream bridge."""

  if not isinstance(bridge, MocCausticUpstreamBridge):
    raise TypeError('bridge must be a MocCausticUpstreamBridge')
  planner = plan_caustic_shock_remesh_chain(
    seed,
    request,
    bridge.state_at,
    bridge.static_pressure_at,
    downstream_invariant_at=downstream_invariant_at,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    maximum_invariant_iterations=maximum_invariant_iterations,
    policy=policy,
    _upstream_bridge=bridge,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'upstream_field_model': 'bounded-old-family-restarted-family-bridge',
    'strict_bridge_required': True,
  })
  return replace(
    planner,
    claim_status=(
      'caustic-shock-remesh strict bridge planner; physical-first-cell-'
      'closure-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_caustic_remesh_downstream_field_chain(
  remesh: MocCausticShockRemeshResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
  allow_research_continuation: bool = False,
) -> MocChainPlannerResult:
  """Continue a converged caustic remesh field in an explicit research lane.

  A coupled caustic remesh produces a bounded post-shock field, but the
  remesh result itself is not a physically closed chain cell: the
  old-family/new-family and downstream physical-boundary claim remains open.
  This wrapper makes the next numerical experiment available without
  weakening that gate.  The caller must explicitly opt into the research
  continuation, and the returned planner remains
  ``UPSTREAM_COUPLED_RESEARCH`` with production claims disabled.

  The remesh field is accepted only after its event, upstream, shock, and
  downstream characteristic-field seam checks pass.  Subsequent cells use
  the existing bounded field-coupled solver; the accepted field is replaced
  only after a complete next-cell solve returns.
  """

  if not isinstance(remesh, MocCausticShockRemeshResult):
    raise TypeError('remesh must be a MocCausticShockRemeshResult')
  if not isinstance(allow_research_continuation, bool):
    raise TypeError('allow_research_continuation must be a bool')
  if not allow_research_continuation:
    raise ValueError(
      'caustic remesh field continuation requires explicit '
      'allow_research_continuation=True; production promotion remains blocked'
    )
  field = remesh.as_bounded_downstream_field()
  planner = plan_post_shock_field_chain(
    field,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    start_point_at=start_point_at,
    end_x_at=end_x_at,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_remesh_continuation': remesh.as_report(),
    'seed_field_model': 'bounded-caustic-remesh-post-shock-field',
    'research_continuation_opt_in': allow_research_continuation,
    'remesh_physical_closure_verified': remesh.physical_closure_verified,
    'remesh_chain_promotion_blocked': remesh.chain_promotion_blocked,
    'upstream_field_replacement_policy': (
      'replace-only-after-complete-field-coupled-solve'
    ),
  })
  return replace(
    planner,
    claim_status=(
      'caustic-remesh-downstream-field research chain; '
      'old-family-seam-and-physical-boundary-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_caustic_remesh_downstream_field_invariant_chain(
  remesh: MocCausticShockRemeshResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[
    [MocPostShockCharacteristicFieldResult, int, tuple[float, float]],
    float,
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
  allow_research_continuation: bool = False,
) -> MocChainPlannerResult:
  """Continue a remeshed field with an explicit invariant boundary law.

  This is the invariant-conditioned counterpart to
  :func:`plan_caustic_remesh_downstream_field_chain`.  The invariant callback
  receives the currently accepted bounded field, so each continued shock is
  still re-solved from carried state/pressure data.  The selected invariant
  is a research boundary condition; it does not supply the missing physical
  caustic seam or mixed-regime closure.
  """

  if not isinstance(remesh, MocCausticShockRemeshResult):
    raise TypeError('remesh must be a MocCausticShockRemeshResult')
  if not isinstance(allow_research_continuation, bool):
    raise TypeError('allow_research_continuation must be a bool')
  if not allow_research_continuation:
    raise ValueError(
      'caustic remesh invariant continuation requires explicit '
      'allow_research_continuation=True; production promotion remains blocked'
    )
  field = remesh.as_bounded_downstream_field()
  planner = plan_post_shock_field_invariant_chain(
    field,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    start_point_at=start_point_at,
    downstream_invariant_family=downstream_invariant_family,
    downstream_invariant_at=downstream_invariant_at,
    end_x_at=end_x_at,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    maximum_invariant_iterations=maximum_invariant_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'caustic_remesh_continuation': remesh.as_report(),
    'seed_field_model': 'bounded-caustic-remesh-post-shock-field',
    'research_continuation_opt_in': allow_research_continuation,
    'downstream_invariant_family': downstream_invariant_family.value,
    'remesh_physical_closure_verified': remesh.physical_closure_verified,
    'remesh_chain_promotion_blocked': remesh.chain_promotion_blocked,
    'upstream_field_replacement_policy': (
      'replace-only-after-complete-field-coupled-solve'
    ),
  })
  return replace(
    planner,
    claim_status=(
      'caustic-remesh-downstream-field invariant research chain; '
      'old-family-seam-and-physical-boundary-pending'
    ),
    diagnostics=diagnostics,
  )


def plan_post_shock_characteristic_chain(
  seed: MocPostShockCharacteristicFieldResult,
  solve_next: MocPostShockFieldContinuationSolver,
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = False,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Plan a state-carrying post-shock chain with exact handoff audit steps."""

  if planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH and not require_upstream_shock_coupling:
    raise ValueError(
      'upstream-coupled research planning requires '
      'require_upstream_shock_coupling=True'
    )
  steps: list[MocChainPlannerStep] = []

  def wrapped(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision | None:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError('planner callback received a handoff different from the current cell')
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      incoming_handoff,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_post_shock_characteristic_chain(
    seed,
    wrapped,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=require_upstream_shock_coupling,
  )
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_euler_companion_field_reference(
  field: MocEulerCompanionFieldResult,
  *,
  claim_status: str | None = None,
) -> MocEulerCompanionFieldPlannerResult:
  """Expose an Euler companion field through the planner safety boundary.

  A converged companion strip is a local characteristic result, not a closed
  shock-cell seed.  The planner therefore retains its typed termination and
  never invokes a continued-cell callback from this adapter.
  """

  if not isinstance(field, MocEulerCompanionFieldResult):
    raise TypeError('field must be a MocEulerCompanionFieldResult')
  termination = field.as_chain_termination_decision()
  return MocEulerCompanionFieldPlannerResult(
    field=field,
    termination=termination,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-euler-companion-field-planner; '
      'global-reflected-free-boundary-and-continued-chain-pending'
      if claim_status is None
      else claim_status
    ),
    diagnostics={
      'planner_model': 'euler-companion-field-boundary-planner',
      'continued_cell_callback_invoked': False,
      'field_status': field.status.value,
      'field_converged': field.converged,
      'field_chain_termination_reason': termination.reason.value,
      'chain_promotion_blocked': True,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
    },
  )
  ####


def plan_euler_companion_field_chain_probe(
  seed: MocPostShockCharacteristicFieldResult,
  field: MocEulerCompanionFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Probe an Euler companion field at the continued-chain boundary.

  The legacy-compatible ``seed`` supplies the already accepted chain prefix
  needed by the generic planner.  The Euler companion field is consumed only
  as the next-cell solver's typed boundary decision; it is intentionally not
  converted into a ``MocChainCell``.  This keeps the high-fidelity Euler lane
  observable in chain reports while the missing reflected closure remains a
  hard stop.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(field, MocEulerCompanionFieldResult):
    raise TypeError('field must be a MocEulerCompanionFieldResult')
  field_planner = plan_euler_companion_field_reference(field)
  boundary_decision = field_planner.termination

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocChainTerminationDecision:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError(
        'Euler companion field chain probe received a changed incoming handoff'
      )
    diagnostics = dict(boundary_decision.diagnostics)
    diagnostics.update({
      'planner_model': 'euler-companion-field-chain-boundary-probe',
      'next_cell_index': next_cell_index,
      'incoming_handoff_sample_count': len(incoming_handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(incoming_handoff),
      'euler_field_consumed_as_chain_seed': False,
    })
    return replace(boundary_decision, diagnostics=diagnostics)

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'euler-companion-field-chain-boundary-probe; '
      'open-reflected-free-boundary-and-continued-euler-chain-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'euler_companion_field_planner': field_planner.as_report(),
      'euler_field_consumed_as_chain_seed': False,
      'continued_cell_callback_policy': (
        'typed-boundary-stop-only-until-global-reflected-closure'
      ),
      'upstream_field_replacement_policy': 'never-replace-on-boundary-probe',
    },
  )
  ####


def plan_euler_companion_field_chain(
  seed: MocEulerCompanionFieldResult,
  solve_next: Callable[
    [
      MocEulerCompanionFieldResult,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocEulerCompanionFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  total_field_count: int,
  position_tolerance_m: float = 1.0e-10,
  claim_status: str | None = None,
) -> MocEulerCompanionFieldChainPlannerResult:
  """Continue open Euler fields through an exact-frontier planner seam.

  This planner is deliberately separate from ``plan_ambient_closed_post_shock_chain``:
  an Euler companion strip has a bounded numerical frontier, but it does not
  have the physical reflected/free-boundary perimeter required for a
  ``MocChainCell``.  A callback may therefore append only another validated
  open field or return a typed non-physical stop.
  """

  if not isinstance(seed, MocEulerCompanionFieldResult):
    raise TypeError('seed must be a MocEulerCompanionFieldResult')
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  if (
    isinstance(total_field_count, bool)
    or not isinstance(total_field_count, int)
    or total_field_count < 1
  ):
    raise ValueError('total_field_count must be a positive integer')
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  fields: list[MocEulerCompanionFieldResult] = [seed]
  steps: list[MocEulerCompanionFieldChainStep] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerCompanionFieldChainPlannerResult:
    return MocEulerCompanionFieldChainPlannerResult(
      seed=seed,
      fields=tuple(fields),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'euler-companion-field-chain-sequence; reflected-free-boundary-and-'
        'entropy-closure-pending'
        if claim_status is None
        else claim_status
      ),
      diagnostics={
        'planner_model': 'euler-companion-field-chain',
        'total_field_count_requested': total_field_count,
        'accepted_field_count': len(fields),
        'open_field_promotion_policy': 'never-create-moc-chain-cell',
        'fresh_domain_tolerance_m': tolerance,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  if not seed.converged:
    return result(seed.as_chain_termination_decision())
  if not seed.state_sampling_available:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'Euler companion field chain requires a state-carrying downstream '
          'frontier on its seed field'
        ),
        diagnostics={
          'seed_field_status': seed.status.value,
          'seed_field_fingerprint': _euler_companion_field_fingerprint(seed),
        },
      )
    )

  def append_step(
    next_field_index: int,
    incoming: tuple[MocChainBoundarySample, ...],
    **values: Any,
  ) -> None:
    steps.append(
      MocEulerCompanionFieldChainStep(
        next_field_index=next_field_index,
        incoming_handoff_sample_count=len(incoming),
        incoming_handoff_fingerprint=_handoff_fingerprint(incoming),
        incoming_handoff_link_verified=values.pop(
          'incoming_handoff_link_verified',
          False,
        ),
        **values,
      )
    )

  for next_field_index in range(2, total_field_count + 2):
    current = fields[-1]
    incoming = current.downstream_handoff
    if not incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'Euler companion field did not retain a state-carrying frontier '
          'for continued planning'
        ),
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
        },
      )
      append_step(
        next_field_index,
        incoming,
        result_kind='termination-returned',
        result_status='state-boundary',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    try:
      solved = solve_next(current, next_field_index, incoming)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'Euler companion field continuation raised: {error}',
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
          'solver_error': type(error).__name__,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='solver-error',
        result_status=type(error).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if solved is None:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='Euler companion field continuation returned no next field',
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='none',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if isinstance(solved, MocChainTerminationDecision):
      if solved.physical_termination:
        termination = MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
          message=(
            'an open Euler companion field cannot declare physical '
            'termination before reflected/free-boundary closure'
          ),
          diagnostics={
            **dict(solved.diagnostics),
            'returned_physical_termination': True,
          },
        )
      else:
        termination = solved
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='decision',
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)

    if not isinstance(solved, MocEulerCompanionFieldContinuationSolve):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=(
          'Euler companion field continuation must return a continuation '
          'solve, typed termination, or None'
        ),
        diagnostics={'returned_type': type(solved).__name__},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='invalid-result-returned',
        result_status=type(solved).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    next_field = solved.field
    field_fingerprint = _euler_companion_field_fingerprint(next_field)
    if solved.incoming_handoff != incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'Euler companion field continuation did not retain the exact '
          'incoming frontier'
        ),
        diagnostics={
          'expected_incoming_handoff_fingerprint': _handoff_fingerprint(incoming),
          'returned_incoming_handoff_fingerprint': _handoff_fingerprint(
            solved.incoming_handoff
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=False,
        result_kind='handoff-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if next_field is current:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='Euler companion field continuation reused the current field object',
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-reuse-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not next_field.converged:
      termination = next_field.as_chain_termination_decision()
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)
    if not next_field.state_sampling_available:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='next Euler companion field has no bounded downstream frontier',
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not (
      next_field.shock_boundary_local_euler_verified
      and next_field.companion_boundary_contract_verified
      and next_field.pressure_lineage_verified
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message=(
          'next Euler companion field lacks its local shock/companion '
          'contract evidence'
        ),
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    current_extent = _euler_companion_field_x_extent(current)
    next_extent = _euler_companion_field_x_extent(next_field)
    if (
      current_extent is None
      or next_extent is None
      or next_extent[0] <= current_extent[1] + tolerance
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'next Euler companion field does not occupy a fresh downstream '
          'domain; no overlap or backtracking was accepted'
        ),
        diagnostics={
          'current_field_x_extent_m': current_extent,
          'next_field_x_extent_m': next_extent,
          'position_tolerance_m': tolerance,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='fresh-domain-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    outgoing = next_field.downstream_handoff
    if not outgoing:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='accepted Euler companion field has no outgoing frontier',
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    fields.append(next_field)
    append_step(
      next_field_index,
      incoming,
      incoming_handoff_link_verified=True,
      result_kind='field-solve-returned',
      result_status=next_field.status.value,
      result_field_status=next_field.status.value,
      result_field_fingerprint=field_fingerprint,
      result_handoff_sample_count=len(outgoing),
      result_handoff_fingerprint=_handoff_fingerprint(outgoing),
    )

  termination = MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.MAX_CELL_LIMIT,
    message='Euler companion field chain reached its configured field limit',
    diagnostics={'total_field_count': total_field_count},
  )
  return result(termination)
  ####


def plan_euler_companion_field_chain_mock(
  seed: MocEulerCompanionFieldResult,
  *,
  mock: MocEulerCompanionFieldChainMock | None = None,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerCompanionFieldChainPlannerResult:
  """Run the translated open-field sequence fixture."""

  fixture = MocEulerCompanionFieldChainMock() if mock is None else mock
  if not isinstance(fixture, MocEulerCompanionFieldChainMock):
    raise TypeError('mock must be a MocEulerCompanionFieldChainMock')
  return plan_euler_companion_field_chain(
    seed,
    fixture.solve_next,
    total_field_count=fixture.total_field_count,
    position_tolerance_m=position_tolerance_m,
    claim_status=(
      'deterministic-euler-companion-field-chain-mock; '
      'reflected-free-boundary-and-entropy-closure-pending'
    ),
  )
  ####


def plan_euler_ambient_shock_field_reference(
  field: MocEulerAmbientShockFieldResult,
  *,
  claim_status: str | None = None,
) -> MocEulerAmbientShockFieldPlannerResult:
  """Expose an exact ambient shock field through the planner boundary."""

  if not isinstance(field, MocEulerAmbientShockFieldResult):
    raise TypeError('field must be a MocEulerAmbientShockFieldResult')
  termination = field.as_chain_termination_decision()
  return MocEulerAmbientShockFieldPlannerResult(
    field=field,
    termination=termination,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-euler-ambient-shock-field-planner; '
      'attachment-aware-first-cell-and-reflected-free-boundary-closure-pending'
      if claim_status is None
      else claim_status
    ),
    diagnostics={
      'planner_model': 'euler-ambient-shock-field-boundary-planner',
      'continued_cell_callback_invoked': False,
      'field_status': field.status.value,
      'field_converged': field.converged,
      'field_fingerprint': _euler_ambient_shock_field_fingerprint(field),
      'field_chain_termination_reason': termination.reason.value,
      'ambient_boundary_verified': field.ambient_boundary_verified,
      'entropy_lineage_verified': field.entropy_lineage_verified,
      'local_field_verified': field.local_field_verified,
      'chain_promotion_blocked': True,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
    },
  )
  ####


def plan_euler_ambient_shock_field_chain(
  seed: MocEulerAmbientShockFieldResult,
  solve_next: Callable[
    [
      MocEulerAmbientShockFieldResult,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocEulerAmbientShockFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  total_field_count: int,
  position_tolerance_m: float = 1.0e-10,
  claim_status: str | None = None,
) -> MocEulerAmbientShockFieldChainPlannerResult:
  """Continue exact ambient shock fields without creating physical cells.

  A callback may append only another converged, locally audited open field
  with a fresh downstream domain.  Attachment-aware first-cell closure,
  entropy transport, and reflected/free-boundary closure remain explicit
  fidelity gates rather than being inferred from a translated topology.
  """

  if not isinstance(seed, MocEulerAmbientShockFieldResult):
    raise TypeError('seed must be a MocEulerAmbientShockFieldResult')
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  if (
    isinstance(total_field_count, bool)
    or not isinstance(total_field_count, int)
    or total_field_count < 1
  ):
    raise ValueError('total_field_count must be a positive integer')
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  fields: list[MocEulerAmbientShockFieldResult] = [seed]
  steps: list[MocEulerAmbientShockFieldChainStep] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientShockFieldChainPlannerResult:
    return MocEulerAmbientShockFieldChainPlannerResult(
      seed=seed,
      fields=tuple(fields),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'euler-ambient-shock-field-chain-sequence; attachment-aware-first-'
        'cell, reflected-free-boundary, and entropy closure pending'
        if claim_status is None
        else claim_status
      ),
      diagnostics={
        'planner_model': 'euler-ambient-shock-field-chain',
        'total_field_count_requested': total_field_count,
        'accepted_field_count': len(fields),
        'open_field_promotion_policy': 'never-create-moc-chain-cell',
        'fresh_domain_tolerance_m': tolerance,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  if not seed.converged:
    return result(seed.as_chain_termination_decision())
  if not seed.state_sampling_available:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'exact ambient shock field chain requires a state-carrying '
          'downstream frontier on its seed field'
        ),
        diagnostics={
          'seed_field_status': seed.status.value,
          'seed_field_fingerprint': _euler_ambient_shock_field_fingerprint(seed),
        },
      )
    )

  def append_step(
    next_field_index: int,
    incoming: tuple[MocChainBoundarySample, ...],
    **values: Any,
  ) -> None:
    steps.append(
      MocEulerAmbientShockFieldChainStep(
        next_field_index=next_field_index,
        incoming_handoff_sample_count=len(incoming),
        incoming_handoff_fingerprint=_handoff_fingerprint(incoming),
        incoming_handoff_link_verified=values.pop(
          'incoming_handoff_link_verified',
          False,
        ),
        **values,
      )
    )

  for next_field_index in range(2, total_field_count + 2):
    current = fields[-1]
    incoming = current.downstream_handoff
    if not incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'exact ambient shock field did not retain a state-carrying '
          'frontier for continued planning'
        ),
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
        },
      )
      append_step(
        next_field_index,
        incoming,
        result_kind='termination-returned',
        result_status='state-boundary',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    try:
      solved = solve_next(current, next_field_index, incoming)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'exact ambient shock field continuation raised: {error}',
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
          'solver_error': type(error).__name__,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='solver-error',
        result_status=type(error).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if solved is None:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'exact ambient shock field continuation returned no next field'
        ),
        diagnostics={
          'current_field_index': len(fields),
          'current_field_status': current.status.value,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='none',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if isinstance(solved, MocChainTerminationDecision):
      if solved.physical_termination:
        termination = MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
          message=(
            'an open exact ambient shock field cannot declare physical '
            'termination before reflected/free-boundary closure'
          ),
          diagnostics={
            **dict(solved.diagnostics),
            'returned_physical_termination': True,
          },
        )
      else:
        termination = solved
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='decision',
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)

    if not isinstance(solved, MocEulerAmbientShockFieldContinuationSolve):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=(
          'exact ambient shock field continuation must return a continuation '
          'solve, typed termination, or None'
        ),
        diagnostics={'returned_type': type(solved).__name__},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='invalid-result-returned',
        result_status=type(solved).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    next_field = solved.field
    field_fingerprint = _euler_ambient_shock_field_fingerprint(next_field)
    if solved.incoming_handoff != incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'exact ambient shock field continuation did not retain the exact '
          'incoming frontier'
        ),
        diagnostics={
          'expected_incoming_handoff_fingerprint': _handoff_fingerprint(incoming),
          'returned_incoming_handoff_fingerprint': _handoff_fingerprint(
            solved.incoming_handoff
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=False,
        result_kind='handoff-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if next_field is current:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'exact ambient shock field continuation reused the current field '
          'object'
        ),
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-reuse-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not next_field.converged:
      termination = next_field.as_chain_termination_decision()
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)
    if not (
      next_field.ambient_boundary_verified
      and next_field.entropy_lineage_verified
      and next_field.local_field_verified
      and next_field.field is not None
      and next_field.field.converged
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message=(
          'next exact ambient shock field lacks its local shock, ambient, '
          'entropy, or companion-field contract evidence'
        ),
        diagnostics={
          'field_fingerprint': field_fingerprint,
          'ambient_boundary_verified': next_field.ambient_boundary_verified,
          'entropy_lineage_verified': next_field.entropy_lineage_verified,
          'local_field_verified': next_field.local_field_verified,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    current_extent = _euler_ambient_shock_field_x_extent(current)
    next_extent = _euler_ambient_shock_field_x_extent(next_field)
    if (
      current_extent is None
      or next_extent is None
      or next_extent[0] <= current_extent[1] + tolerance
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'next exact ambient shock field does not occupy a fresh downstream '
          'domain; no overlap or backtracking was accepted'
        ),
        diagnostics={
          'current_field_x_extent_m': current_extent,
          'next_field_x_extent_m': next_extent,
          'position_tolerance_m': tolerance,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='fresh-domain-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    outgoing = next_field.downstream_handoff
    if not outgoing:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='accepted exact ambient shock field has no outgoing frontier',
        diagnostics={'field_fingerprint': field_fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=field_fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    fields.append(next_field)
    append_step(
      next_field_index,
      incoming,
      incoming_handoff_link_verified=True,
      result_kind='field-solve-returned',
      result_status=next_field.status.value,
      result_field_status=next_field.status.value,
      result_field_fingerprint=field_fingerprint,
      result_handoff_sample_count=len(outgoing),
      result_handoff_fingerprint=_handoff_fingerprint(outgoing),
    )

  termination = MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.MAX_CELL_LIMIT,
    message=(
      'exact ambient shock field chain reached its configured field limit'
    ),
    diagnostics={'total_field_count': total_field_count},
  )
  return result(termination)
  ####


def plan_euler_ambient_shock_field_chain_mock(
  seed: MocEulerAmbientShockFieldResult,
  *,
  mock: MocEulerAmbientShockFieldChainMock | None = None,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientShockFieldChainPlannerResult:
  """Run the translated exact-open-field sequence fixture."""

  fixture = (
    MocEulerAmbientShockFieldChainMock() if mock is None else mock
  )
  if not isinstance(fixture, MocEulerAmbientShockFieldChainMock):
    raise TypeError('mock must be a MocEulerAmbientShockFieldChainMock')
  return plan_euler_ambient_shock_field_chain(
    seed,
    fixture.solve_next,
    total_field_count=fixture.total_field_count,
    position_tolerance_m=position_tolerance_m,
    claim_status=(
      'deterministic-euler-ambient-shock-field-chain-mock; attachment-aware-'
      'first-cell, reflected-free-boundary, and entropy closure pending'
    ),
  )
  ####


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldContinuationSolve:
  """One local post-shock field and the exact frontier it consumed."""

  field: MocEulerPostShockFieldResult
  incoming_handoff: tuple[MocChainBoundarySample, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocEulerPostShockFieldResult):
      raise TypeError('field must be a MocEulerPostShockFieldResult')
    handoff = tuple(self.incoming_handoff)
    if not handoff:
      raise ValueError('incoming_handoff must contain state-carrying samples')
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', handoff)

  @property
  def outgoing_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    return self.field.downstream_handoff

  def as_report(self) -> dict[str, Any]:
    return {
      'field_status': self.field.status.value,
      'field_converged': self.field.converged,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(self.incoming_handoff),
      'outgoing_handoff_sample_count': len(self.outgoing_handoff),
      'outgoing_handoff_fingerprint': _handoff_fingerprint(self.outgoing_handoff),
      'field_fingerprint': _euler_post_shock_field_fingerprint(self.field),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldChainStep:
  """One callback attempt in a local post-shock field sequence."""

  next_field_index: int
  incoming_handoff_sample_count: int
  incoming_handoff_fingerprint: str | None
  incoming_handoff_link_verified: bool
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_field_status: str | None = None
  result_field_fingerprint: str | None = None
  result_handoff_sample_count: int | None = None
  result_handoff_fingerprint: str | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.next_field_index, bool)
      or not isinstance(self.next_field_index, int)
      or self.next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    if (
      isinstance(self.incoming_handoff_sample_count, bool)
      or not isinstance(self.incoming_handoff_sample_count, int)
      or self.incoming_handoff_sample_count < 0
    ):
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    if not isinstance(self.incoming_handoff_link_verified, bool):
      raise TypeError('incoming_handoff_link_verified must be a bool')
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    for name in (
      'incoming_handoff_fingerprint',
      'result_status',
      'result_field_status',
      'result_field_fingerprint',
      'result_handoff_fingerprint',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if self.result_handoff_sample_count is not None and (
      isinstance(self.result_handoff_sample_count, bool)
      or not isinstance(self.result_handoff_sample_count, int)
      or self.result_handoff_sample_count < 0
    ):
      raise ValueError('result_handoff_sample_count must be nonnegative')
    if self.result_termination_reason is not None and not isinstance(
      self.result_termination_reason,
      MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
      self.result_physical_termination,
      bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')

  def as_report(self) -> dict[str, Any]:
    return {
      'next_field_index': self.next_field_index,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_field_status': self.result_field_status,
      'result_field_fingerprint': self.result_field_fingerprint,
      'result_handoff_sample_count': self.result_handoff_sample_count,
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
    }


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldChainPlannerResult:
  """A research-only sequence of locally closed post-shock fields."""

  seed: MocEulerPostShockFieldResult
  fields: tuple[MocEulerPostShockFieldResult, ...]
  steps: tuple[MocEulerPostShockFieldChainStep, ...]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerPostShockFieldResult):
      raise TypeError('seed must be a MocEulerPostShockFieldResult')
    fields = tuple(self.fields)
    if not fields or fields[0] is not self.seed:
      raise ValueError('fields must retain the seed field as their first entry')
    if any(not isinstance(value, MocEulerPostShockFieldResult) for value in fields):
      raise TypeError(
        'fields must contain MocEulerPostShockFieldResult values'
      )
    steps = tuple(self.steps)
    if any(
      not isinstance(value, MocEulerPostShockFieldChainStep)
      for value in steps
    ):
      raise TypeError(
        'steps must contain MocEulerPostShockFieldChainStep values'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'local post-shock field chains must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'fields', fields)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def field_count(self) -> int:
    return len(self.fields)

  @property
  def continued_field_count(self) -> int:
    return max(0, len(self.fields) - 1)

  @property
  def resolved(self) -> bool:
    return bool(
      self.fields
      and all(field.converged for field in self.fields)
      and self.termination.reason
      is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    )

  @property
  def handoff_links_verified(self) -> bool | None:
    if not self.steps:
      return None
    return all(step.incoming_handoff_link_verified for step in self.steps)

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'handoff_links_verified': self.handoff_links_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fields': [field.as_report() for field in self.fields],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshPlannerStep:
  """One deterministic local remesh attempt in the pre-chain planner."""

  subdivision_level: int
  source_field_status: str
  result_status: str
  result_kind: str
  result_converged: bool
  result_cell_count: int
  result_state_sample_count: int
  result_topology_verified: bool
  result_state_projection_verified: bool
  result_pressure_lineage_carried: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    if (
      isinstance(self.subdivision_level, bool)
      or not isinstance(self.subdivision_level, int)
      or self.subdivision_level < 1
    ):
      raise ValueError('subdivision_level must be a positive integer')
    for name in ('source_field_status', 'result_status', 'result_kind'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    for name in ('result_cell_count', 'result_state_sample_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in (
      'result_converged',
      'result_topology_verified',
      'result_state_projection_verified',
      'result_pressure_lineage_carried',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')

  def as_report(self) -> dict[str, Any]:
    return {
      'subdivision_level': self.subdivision_level,
      'source_field_status': self.source_field_status,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_cell_count': self.result_cell_count,
      'result_state_sample_count': self.result_state_sample_count,
      'checks': {
        'topology_verified': self.result_topology_verified,
        'state_projection_verified': self.result_state_projection_verified,
        'pressure_lineage_carried': self.result_pressure_lineage_carried,
        'physical_closure_verified': self.result_physical_closure_verified,
        'chain_promotion_blocked': self.result_chain_promotion_blocked,
        'production_claim_allowed': self.result_production_claim_allowed,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshPlannerResult:
  """A research-only first-wedge remesh ladder and explicit chain stop."""

  seed: MocEulerAmbientPhysicalFieldResult
  remeshes: tuple[MocEulerAmbientFirstWedgeRemeshResult, ...]
  steps: tuple[MocEulerAmbientFirstWedgeRemeshPlannerStep, ...]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerAmbientPhysicalFieldResult):
      raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
    remeshes = tuple(self.remeshes)
    if any(
      not isinstance(value, MocEulerAmbientFirstWedgeRemeshResult)
      for value in remeshes
    ):
      raise TypeError(
        'remeshes must contain MocEulerAmbientFirstWedgeRemeshResult values'
      )
    steps = tuple(self.steps)
    if len(steps) != len(remeshes):
      raise ValueError('steps must align with remeshes')
    if any(
      not isinstance(value, MocEulerAmbientFirstWedgeRemeshPlannerStep)
      for value in steps
    ):
      raise TypeError(
        'steps must contain MocEulerAmbientFirstWedgeRemeshPlannerStep values'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'first-wedge remesh planner must use the upstream-coupled research '
        'planner kind'
      )
    object.__setattr__(self, 'remeshes', remeshes)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def remesh_count(self) -> int:
    return len(self.remeshes)

  @property
  def resolved(self) -> bool:
    """Whether every requested diagnostic subdivision assembled."""

    return bool(
      self.remeshes
      and all(remesh.converged for remesh in self.remeshes)
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def first_wedge_subdivision_verified(self) -> bool:
    if len(self.remeshes) < 2:
      return False
    return all(
      right.cell_count > left.cell_count
      for left, right in zip(self.remeshes, self.remeshes[1:])
    )

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'remesh_count': self.remesh_count,
      'subdivision_levels': [
        remesh.subdivision_level for remesh in self.remeshes
      ],
      'cell_counts': [remesh.cell_count for remesh in self.remeshes],
      'first_wedge_subdivision_verified': (
        self.first_wedge_subdivision_verified
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'remeshes': [remesh.as_report() for remesh in self.remeshes],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_remesh_mock(
  seed: MocEulerAmbientPhysicalFieldResult,
  *,
  subdivision_levels: Sequence[int] = (1, 2, 3),
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientFirstWedgeRemeshPlannerResult:
  """Run bounded wedge subdivisions and stop before physical promotion.

  This planner is a deterministic research mock around the solver-owned
  local remesh seam.  It records the growing diagnostic mesh, but does not
  turn the projected states into ``MocChainCell`` objects.
  """

  if not isinstance(seed, MocEulerAmbientPhysicalFieldResult):
    raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
  try:
    levels = tuple(subdivision_levels)
  except TypeError as error:
    raise ValueError('subdivision_levels must be an iterable of integers') from error
  if len(levels) < 2 or any(
    isinstance(level, bool) or not isinstance(level, int) or level < 1
    for level in levels
  ):
    raise ValueError(
      'subdivision_levels must contain at least two positive integers'
    )
  if any(right <= left for left, right in zip(levels, levels[1:])):
    raise ValueError('subdivision_levels must be strictly increasing')
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  remeshes: list[MocEulerAmbientFirstWedgeRemeshResult] = []
  steps: list[MocEulerAmbientFirstWedgeRemeshPlannerStep] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeRemeshPlannerResult:
    return MocEulerAmbientFirstWedgeRemeshPlannerResult(
      seed=seed,
      remeshes=tuple(remeshes),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'deterministic-euler-ambient-first-wedge-remesh-mock; conservative '
        'terminal-wedge solve, reflected free-boundary closure, and external '
        'validation pending'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-remesh-mock',
        'requested_subdivision_levels': levels,
        'position_tolerance_m': tolerance,
        'accepted_remesh_count': len(remeshes),
        'local_remesh_policy': (
          'bounded-state-projection-only; never-create-moc-chain-cell'
        ),
        'independent_audit_required': True,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  if not seed.converged:
    return result(seed.as_chain_termination_decision())
  for level in levels:
    try:
      remesh = remesh_euler_ambient_first_wedge(
        seed,
        subdivision_level=level,
        position_tolerance_m=tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'first-wedge remesh mock raised: {error}',
        diagnostics={
          'planner_model': 'euler-ambient-first-wedge-remesh-mock',
          'subdivision_level': level,
          'solver_error': type(error).__name__,
        },
      )
      return result(termination)
    remeshes.append(remesh)
    steps.append(
      MocEulerAmbientFirstWedgeRemeshPlannerStep(
        subdivision_level=level,
        source_field_status=seed.status.value,
        result_status=remesh.status.value,
        result_kind='diagnostic-remesh-returned',
        result_converged=remesh.converged,
        result_cell_count=remesh.cell_count,
        result_state_sample_count=remesh.state_sample_count,
        result_topology_verified=bool(
          remesh.topology.connected
          and remesh.topology.forms_closed_zone
          and remesh.topology.nonmanifold_edge_count == 0
        ),
        result_state_projection_verified=remesh.state_projection_verified,
        result_pressure_lineage_carried=remesh.pressure_lineage_carried,
        result_physical_closure_verified=remesh.physical_closure_verified,
        result_chain_promotion_blocked=remesh.chain_promotion_blocked,
        result_production_claim_allowed=remesh.production_claim_allowed,
      )
    )
    if not remesh.converged:
      return result(remesh.as_chain_termination_decision())

  return result(
    MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
      message=(
        'diagnostic first-wedge remesh ladder completed; conservative '
        'terminal-wedge closure is required before a shock-cell chain can '
        'consume the result'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-remesh-mock',
        'subdivision_levels': levels,
        'cell_counts': tuple(remesh.cell_count for remesh in remeshes),
        'required_next_gate': (
          'independent-remesh-euler-audit-and-solver-owned-terminal-wedge-'
          'characteristic-closure'
        ),
      },
    )
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicPlannerStep:
  """One solver-owned terminal-wedge attempt before chain promotion."""

  source_field_status: str
  result_status: str
  result_kind: str
  result_converged: bool
  result_characteristic_edge_count: int
  result_topology_verified: bool
  result_characteristic_geometry_verified: bool
  result_variable_entropy_compatibility_verified: bool
  result_cell_euler_residual_verified: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    for name in ('source_field_status', 'result_status', 'result_kind'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    if (
      isinstance(self.result_characteristic_edge_count, bool)
      or not isinstance(self.result_characteristic_edge_count, int)
      or self.result_characteristic_edge_count < 0
    ):
      raise ValueError(
        'result_characteristic_edge_count must be a nonnegative integer'
      )
    for name in (
      'result_converged',
      'result_topology_verified',
      'result_characteristic_geometry_verified',
      'result_variable_entropy_compatibility_verified',
      'result_cell_euler_residual_verified',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')

  def as_report(self) -> dict[str, Any]:
    return {
      'source_field_status': self.source_field_status,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_characteristic_edge_count': self.result_characteristic_edge_count,
      'checks': {
        'topology_verified': self.result_topology_verified,
        'characteristic_geometry_verified': (
          self.result_characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.result_variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.result_cell_euler_residual_verified,
        'physical_closure_verified': self.result_physical_closure_verified,
        'chain_promotion_blocked': self.result_chain_promotion_blocked,
        'production_claim_allowed': self.result_production_claim_allowed,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicPlannerResult:
  """A terminal-wedge attempt and its explicit pre-chain fidelity stop."""

  seed: MocEulerAmbientPhysicalFieldResult
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult | None
  step: MocEulerAmbientFirstWedgeCharacteristicPlannerStep | None
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerAmbientPhysicalFieldResult):
      raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError(
        'candidate must be a MocEulerAmbientFirstWedgeCharacteristicResult or None'
      )
    if self.step is not None and not isinstance(
      self.step,
      MocEulerAmbientFirstWedgeCharacteristicPlannerStep,
    ):
      raise TypeError(
        'step must be a MocEulerAmbientFirstWedgeCharacteristicPlannerStep or None'
      )
    if (self.candidate is None) != (self.step is None):
      raise ValueError('candidate and step must be supplied together')
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'terminal-wedge planner must use the upstream-coupled research '
        'planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def attempted(self) -> bool:
    return self.candidate is not None

  @property
  def resolved(self) -> bool:
    """Whether the candidate attempt reached a typed non-physical stop."""

    return bool(
      self.candidate is not None
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def physical_chain_cell_count(self) -> int:
    """Number of physical chain cells contributed by this planner."""

    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'attempted': self.attempted,
      'resolved': self.resolved,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'step': None if self.step is None else self.step.as_report(),
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_characteristic_remesh(
  seed: MocEulerAmbientPhysicalFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeCharacteristicPlannerResult:
  """Plan one terminal-wedge solve and stop before a physical chain cell.

  The candidate is retained for inspection even when one of its local gates
  fails.  This planner never appends a ``MocChainCell`` and never treats a
  local reflected wedge as evidence of a completed continued shock chain.
  """

  if not isinstance(seed, MocEulerAmbientPhysicalFieldResult):
    raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError) as error:
    raise ValueError('terminal-wedge planner tolerances must be numeric') from error
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult | None = None
  step: MocEulerAmbientFirstWedgeCharacteristicPlannerStep | None = None

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeCharacteristicPlannerResult:
    return MocEulerAmbientFirstWedgeCharacteristicPlannerResult(
      seed=seed,
      candidate=candidate,
      step=step,
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'solver-owned-terminal-characteristic-wedge-planner; global '
        'entropy-carrying remesh, reflected free-boundary closure, and '
        'external validation pending'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-terminal-characteristic',
        'candidate_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'local_candidate_policy': 'retain-for-audit; never-create-moc-chain-cell',
        'position_tolerance_m': position_tolerance,
        'characteristic_residual_tolerance': float(
          residual_tolerance
        ),
        'edge_alignment_tolerance': alignment_tolerance,
        'cell_residual_tolerance': cell_tolerance,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  try:
    candidate = solve_euler_ambient_first_wedge_characteristic_remesh(
      seed,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=residual_tolerance,
      edge_alignment_tolerance=alignment_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'terminal-wedge characteristic planner raised: {error}',
        diagnostics={
          'planner_model': 'euler-ambient-first-wedge-terminal-characteristic',
          'solver_error': type(error).__name__,
          'candidate_consumed_as_chain_cell': False,
        },
      )
    )
  step = MocEulerAmbientFirstWedgeCharacteristicPlannerStep(
    source_field_status=seed.status.value,
    result_status=candidate.status.value,
    result_kind='solver-owned-terminal-wedge-candidate',
    result_converged=candidate.converged,
    result_characteristic_edge_count=len(candidate.characteristic_edges),
    result_topology_verified=bool(
      candidate.topology.connected
      and candidate.topology.forms_closed_zone
      and candidate.topology.nonmanifold_edge_count == 0
    ),
    result_characteristic_geometry_verified=(
      candidate.characteristic_geometry_verified
    ),
    result_variable_entropy_compatibility_verified=(
      candidate.variable_entropy_compatibility_verified
    ),
    result_cell_euler_residual_verified=candidate.cell_euler_residual_verified,
    result_physical_closure_verified=candidate.physical_closure_verified,
    result_chain_promotion_blocked=candidate.chain_promotion_blocked,
    result_production_claim_allowed=candidate.production_claim_allowed,
  )
  return result(candidate.as_chain_termination_decision())


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep:
  """One solver-owned local field-retile attempt before chain promotion."""

  source_field_status: str
  result_status: str
  result_kind: str
  result_converged: bool
  result_retiled_field_status: str | None
  result_replaced_cell_count: int
  result_topology_verified: bool
  result_boundary_paths_verified: bool
  result_terminal_geometry_verified: bool
  result_variable_entropy_compatibility_verified: bool
  result_cell_euler_residual_verified: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    for name in ('source_field_status', 'result_status', 'result_kind'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    if self.result_retiled_field_status is not None:
      if not isinstance(self.result_retiled_field_status, str) or not self.result_retiled_field_status:
        raise ValueError('result_retiled_field_status must be a non-empty string or None')
    if (
      isinstance(self.result_replaced_cell_count, bool)
      or not isinstance(self.result_replaced_cell_count, int)
      or self.result_replaced_cell_count < 0
    ):
      raise ValueError('result_replaced_cell_count must be a nonnegative integer')
    for name in (
      'result_converged',
      'result_topology_verified',
      'result_boundary_paths_verified',
      'result_terminal_geometry_verified',
      'result_variable_entropy_compatibility_verified',
      'result_cell_euler_residual_verified',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')

  def as_report(self) -> dict[str, Any]:
    return {
      'source_field_status': self.source_field_status,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_retiled_field_status': self.result_retiled_field_status,
      'result_replaced_cell_count': self.result_replaced_cell_count,
      'checks': {
        'topology_verified': self.result_topology_verified,
        'boundary_paths_verified': self.result_boundary_paths_verified,
        'terminal_geometry_verified': self.result_terminal_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.result_variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.result_cell_euler_residual_verified,
        'physical_closure_verified': self.result_physical_closure_verified,
        'chain_promotion_blocked': self.result_chain_promotion_blocked,
        'production_claim_allowed': self.result_production_claim_allowed,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicFieldPlannerResult:
  """A local field retile and its explicit pre-chain fidelity stop."""

  seed: MocEulerAmbientPhysicalFieldResult
  field_retile: MocEulerAmbientFirstWedgeCharacteristicFieldResult | None
  step: MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep | None
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocEulerAmbientPhysicalFieldResult):
      raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
    if self.field_retile is not None and not isinstance(
      self.field_retile,
      MocEulerAmbientFirstWedgeCharacteristicFieldResult,
    ):
      raise TypeError(
        'field_retile must be a '
        'MocEulerAmbientFirstWedgeCharacteristicFieldResult or None'
      )
    if self.step is not None and not isinstance(
      self.step,
      MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep,
    ):
      raise TypeError(
        'step must be a '
        'MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep or None'
      )
    if (self.field_retile is None) != (self.step is None):
      raise ValueError('field_retile and step must be supplied together')
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'characteristic field-retile planner must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

  @property
  def attempted(self) -> bool:
    return self.field_retile is not None

  @property
  def resolved(self) -> bool:
    """Whether the retile attempt reached a typed non-physical stop."""

    return bool(
      self.field_retile is not None
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'attempted': self.attempted,
      'resolved': self.resolved,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'field_retile': (
        None if self.field_retile is None else self.field_retile.as_report()
      ),
      'step': None if self.step is None else self.step.as_report(),
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_characteristic_field(
  seed: MocEulerAmbientPhysicalFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeCharacteristicFieldPlannerResult:
  """Plan the local field retile and stop before a physical chain cell."""

  if not isinstance(seed, MocEulerAmbientPhysicalFieldResult):
    raise TypeError('seed must be a MocEulerAmbientPhysicalFieldResult')
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError) as error:
    raise ValueError('characteristic field planner tolerances must be numeric') from error
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  field_retile: MocEulerAmbientFirstWedgeCharacteristicFieldResult | None = None
  step: MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep | None = None

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeCharacteristicFieldPlannerResult:
    return MocEulerAmbientFirstWedgeCharacteristicFieldPlannerResult(
      seed=seed,
      field_retile=field_retile,
      step=step,
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'solver-owned-terminal-characteristic-field-retile-planner; '
        'multi-cell entropy transport, reflected free-boundary continuation, '
        'and external validation pending'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-characteristic-field-retile',
        'retile_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'local_retile_policy': 'retain-for-audit; never-create-moc-chain-cell',
        'position_tolerance_m': position_tolerance,
        'characteristic_residual_tolerance': residual_tolerance,
        'edge_alignment_tolerance': alignment_tolerance,
        'cell_residual_tolerance': cell_tolerance,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  try:
    field_retile = remesh_euler_ambient_first_wedge_characteristic_field(
      seed,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=residual_tolerance,
      edge_alignment_tolerance=alignment_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'characteristic field-retile planner raised: {error}',
        diagnostics={
          'planner_model': 'euler-ambient-first-wedge-characteristic-field-retile',
          'solver_error': type(error).__name__,
          'retile_consumed_as_chain_cell': False,
        },
      )
    )
  step = MocEulerAmbientFirstWedgeCharacteristicFieldPlannerStep(
    source_field_status=seed.status.value,
    result_status=field_retile.status.value,
    result_kind='solver-owned-terminal-characteristic-field-retile',
    result_converged=field_retile.converged,
    result_retiled_field_status=(
      None
      if field_retile.retiled_field is None
      else field_retile.retiled_field.status.value
    ),
    result_replaced_cell_count=len(field_retile.replaced_cell_indices),
    result_topology_verified=field_retile.retiled_field_topology_verified,
    result_boundary_paths_verified=field_retile.boundary_paths_verified,
    result_terminal_geometry_verified=field_retile.terminal_geometry_verified,
    result_variable_entropy_compatibility_verified=(
      field_retile.variable_entropy_compatibility_verified
    ),
    result_cell_euler_residual_verified=field_retile.cell_euler_residual_verified,
    result_physical_closure_verified=field_retile.physical_closure_verified,
    result_chain_promotion_blocked=field_retile.chain_promotion_blocked,
    result_production_claim_allowed=field_retile.production_claim_allowed,
  )
  return result(field_retile.as_chain_termination_decision())


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryPlannerStep:
  """One entropy-carrying terminal trial before chain promotion."""

  source_candidate_status: str
  result_status: str
  result_kind: str
  result_converged: bool
  result_solver_iterations: int
  result_characteristic_edge_count: int
  result_incoming_characteristic_geometry_verified: bool
  result_pressure_lineage_verified: bool
  result_characteristic_geometry_verified: bool
  result_variable_entropy_compatibility_verified: bool
  result_axis_streamline_entropy_verified: bool
  result_cell_euler_residual_finite: bool
  result_cell_euler_residual_verified: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    for name in (
      'source_candidate_status',
      'result_status',
      'result_kind',
    ):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    for name in ('result_solver_iterations', 'result_characteristic_edge_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in (
      'result_converged',
      'result_incoming_characteristic_geometry_verified',
      'result_pressure_lineage_verified',
      'result_characteristic_geometry_verified',
      'result_variable_entropy_compatibility_verified',
      'result_axis_streamline_entropy_verified',
      'result_cell_euler_residual_finite',
      'result_cell_euler_residual_verified',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')

  def as_report(self) -> dict[str, Any]:
    return {
      'source_candidate_status': self.source_candidate_status,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_solver_iterations': self.result_solver_iterations,
      'result_characteristic_edge_count': self.result_characteristic_edge_count,
      'checks': {
        'incoming_characteristic_geometry_verified': (
          self.result_incoming_characteristic_geometry_verified
        ),
        'pressure_lineage_verified': self.result_pressure_lineage_verified,
        'characteristic_geometry_verified': (
          self.result_characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.result_variable_entropy_compatibility_verified
        ),
        'axis_streamline_entropy_verified': (
          self.result_axis_streamline_entropy_verified
        ),
        'cell_euler_residual_finite': self.result_cell_euler_residual_finite,
        'cell_euler_residual_verified': self.result_cell_euler_residual_verified,
        'physical_closure_verified': self.result_physical_closure_verified,
        'chain_promotion_blocked': self.result_chain_promotion_blocked,
        'production_claim_allowed': self.result_production_claim_allowed,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryPlannerResult:
  """An entropy-carrying local trial and its explicit pre-chain stop."""

  seed: MocEulerAmbientFirstWedgeCharacteristicResult
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None
  step: MocEulerAmbientFirstWedgeEntropyCarryPlannerStep | None
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.seed,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError(
        'seed must be a MocEulerAmbientFirstWedgeCharacteristicResult'
      )
    if self.entropy_carry is not None and not isinstance(
      self.entropy_carry,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError(
        'entropy_carry must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryResult or None'
      )
    if self.step is not None and not isinstance(
      self.step,
      MocEulerAmbientFirstWedgeEntropyCarryPlannerStep,
    ):
      raise TypeError(
        'step must be a MocEulerAmbientFirstWedgeEntropyCarryPlannerStep or None'
      )
    if (self.entropy_carry is None) != (self.step is None):
      raise ValueError('entropy_carry and step must be supplied together')
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'entropy-carrying planner must use the upstream-coupled research '
        'planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )

  @property
  def attempted(self) -> bool:
    return self.entropy_carry is not None

  @property
  def resolved(self) -> bool:
    return bool(
      self.entropy_carry is not None
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'attempted': self.attempted,
      'resolved': self.resolved,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'entropy_carry': (
        None
        if self.entropy_carry is None
        else self.entropy_carry.as_report()
      ),
      'step': None if self.step is None else self.step.as_report(),
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_entropy_carry(
  seed: MocEulerAmbientFirstWedgeCharacteristicResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  maximum_iterations: int = 24,
) -> MocEulerAmbientFirstWedgeEntropyCarryPlannerResult:
  """Plan one entropy-carrying terminal trial and stop before a chain cell."""

  if not isinstance(seed, MocEulerAmbientFirstWedgeCharacteristicResult):
    raise TypeError(
      'seed must be a MocEulerAmbientFirstWedgeCharacteristicResult'
    )
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None = None
  step: MocEulerAmbientFirstWedgeEntropyCarryPlannerStep | None = None

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeEntropyCarryPlannerResult:
    return MocEulerAmbientFirstWedgeEntropyCarryPlannerResult(
      seed=seed,
      entropy_carry=entropy_carry,
      step=step,
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'solver-owned-terminal-entropy-carrying-planner; characteristic '
        'subcell refinement, reflected free-boundary continuation, and '
        'external validation pending'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-entropy-carry',
        'entropy_carry_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'local_entropy_policy': (
          'preserve-axis-shock-lineage-and-ambient-off-axis-lineage; '
          'never-create-moc-chain-cell'
        ),
        'independent_audit_required': True,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  try:
    entropy_carry = solve_euler_ambient_first_wedge_entropy_carry(
      seed,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      edge_alignment_tolerance=edge_alignment_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      maximum_iterations=maximum_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'entropy-carrying planner raised: {error}',
        diagnostics={
          'planner_model': 'euler-ambient-first-wedge-entropy-carry',
          'solver_error': type(error).__name__,
          'entropy_carry_consumed_as_chain_cell': False,
        },
      )
    )
  step = MocEulerAmbientFirstWedgeEntropyCarryPlannerStep(
    source_candidate_status=seed.status.value,
    result_status=entropy_carry.status.value,
    result_kind='solver-owned-terminal-entropy-carrying-trial',
    result_converged=entropy_carry.converged,
    result_solver_iterations=entropy_carry.solver_iterations,
    result_characteristic_edge_count=len(entropy_carry.characteristic_edges),
    result_incoming_characteristic_geometry_verified=(
      entropy_carry.incoming_characteristic_geometry_verified
    ),
    result_pressure_lineage_verified=entropy_carry.pressure_lineage_verified,
    result_characteristic_geometry_verified=(
      entropy_carry.characteristic_geometry_verified
    ),
    result_variable_entropy_compatibility_verified=(
      entropy_carry.variable_entropy_compatibility_verified
    ),
    result_axis_streamline_entropy_verified=(
      entropy_carry.axis_streamline_entropy_verified
    ),
    result_cell_euler_residual_finite=entropy_carry.cell_euler_residual_finite,
    result_cell_euler_residual_verified=entropy_carry.cell_euler_residual_verified,
    result_physical_closure_verified=entropy_carry.physical_closure_verified,
    result_chain_promotion_blocked=entropy_carry.chain_promotion_blocked,
    result_production_claim_allowed=entropy_carry.production_claim_allowed,
  )
  return result(entropy_carry.as_chain_termination_decision())


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep:
  """One internal entropy-characteristic field attempt before chain promotion."""

  source_trial_status: str
  result_status: str
  result_kind: str
  result_converged: bool
  result_solver_iterations: int
  result_node_count: int
  result_cell_count: int
  result_characteristic_edge_count: int
  result_continuation_boundary_sample_count: int
  result_continuation_boundary_verified: bool
  result_topology_verified: bool
  result_pressure_lineage_verified: bool
  result_characteristic_geometry_verified: bool
  result_variable_entropy_compatibility_verified: bool
  result_cell_euler_residuals_verified: bool
  result_internal_characteristic_closure_verified: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    for name in ('source_trial_status', 'result_status', 'result_kind'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    for name in (
      'result_solver_iterations',
      'result_node_count',
      'result_cell_count',
      'result_characteristic_edge_count',
      'result_continuation_boundary_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in (
      'result_converged',
      'result_continuation_boundary_verified',
      'result_topology_verified',
      'result_pressure_lineage_verified',
      'result_characteristic_geometry_verified',
      'result_variable_entropy_compatibility_verified',
      'result_cell_euler_residuals_verified',
      'result_internal_characteristic_closure_verified',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')

  def as_report(self) -> dict[str, Any]:
    return {
      'source_trial_status': self.source_trial_status,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_solver_iterations': self.result_solver_iterations,
    'result_node_count': self.result_node_count,
    'result_cell_count': self.result_cell_count,
    'result_characteristic_edge_count': self.result_characteristic_edge_count,
    'result_continuation_boundary_sample_count': (
      self.result_continuation_boundary_sample_count
    ),
      'checks': {
        'topology_verified': self.result_topology_verified,
        'pressure_lineage_verified': self.result_pressure_lineage_verified,
        'characteristic_geometry_verified': (
          self.result_characteristic_geometry_verified
        ),
      'variable_entropy_compatibility_verified': (
        self.result_variable_entropy_compatibility_verified
      ),
      'continuation_boundary_verified': self.result_continuation_boundary_verified,
        'cell_euler_residuals_verified': (
          self.result_cell_euler_residuals_verified
        ),
        'internal_characteristic_closure_verified': (
          self.result_internal_characteristic_closure_verified
        ),
        'physical_closure_verified': self.result_physical_closure_verified,
        'chain_promotion_blocked': self.result_chain_promotion_blocked,
        'production_claim_allowed': self.result_production_claim_allowed,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerResult:
  """An internal characteristic field and its hard pre-chain stop."""

  seed: MocEulerAmbientFirstWedgeEntropyCarryResult
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  step: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep | None
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.seed,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError(
        'seed must be a MocEulerAmbientFirstWedgeEntropyCarryResult'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'field must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult or None'
      )
    if self.step is not None and not isinstance(
      self.step,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep,
    ):
      raise TypeError(
        'step must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep or None'
      )
    if (self.field is None) != (self.step is None):
      raise ValueError('field and step must be supplied together')
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'internal entropy-characteristic field planner must use the '
        'upstream-coupled research planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )

  @property
  def attempted(self) -> bool:
    return self.field is not None

  @property
  def resolved(self) -> bool:
    return bool(
      self.field is not None
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'attempted': self.attempted,
      'resolved': self.resolved,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'field': None if self.field is None else self.field.as_report(),
      'step': None if self.step is None else self.step.as_report(),
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_entropy_characteristic_field(
  seed: MocEulerAmbientFirstWedgeEntropyCarryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  compatibility_weight: float = 1.0e7,
  maximum_iterations: int = 48,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerResult:
  """Run the internal field solver and stop before a physical chain cell."""

  if not isinstance(seed, MocEulerAmbientFirstWedgeEntropyCarryResult):
    raise TypeError(
      'seed must be a MocEulerAmbientFirstWedgeEntropyCarryResult'
    )
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None = None
  step: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep | None = None

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerResult:
    return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerResult(
      seed=seed,
      field=field,
      step=step,
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'solver-owned-internal-entropy-characteristic-field-planner; '
        'reflected free-boundary coupling, external validation, and continued '
        'shock-cell-chain promotion remain pending'
      ),
      diagnostics={
        'planner_model': (
          'euler-ambient-first-wedge-entropy-characteristic-field'
        ),
        'field_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'internal_characteristic_closure_verified': (
          False if field is None else field.internal_characteristic_closure_verified
        ),
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'independent_audit_required': True,
      },
    )

  try:
    field = solve_euler_ambient_first_wedge_entropy_characteristic_field(
      seed,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      edge_alignment_tolerance=edge_alignment_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      compatibility_weight=compatibility_weight,
      maximum_iterations=maximum_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'internal entropy-characteristic planner raised: {error}',
        diagnostics={
          'planner_model': (
            'euler-ambient-first-wedge-entropy-characteristic-field'
          ),
          'solver_error': type(error).__name__,
          'field_consumed_as_chain_cell': False,
          'physical_chain_cell_count': 0,
        },
      )
    )
  step = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldPlannerStep(
    source_trial_status=seed.status.value,
    result_status=field.status.value,
    result_kind='solver-owned-internal-entropy-characteristic-field',
    result_converged=field.converged,
    result_solver_iterations=field.solver_iterations,
    result_node_count=field.node_count,
    result_cell_count=field.cell_count,
    result_characteristic_edge_count=len(field.characteristic_edges),
    result_continuation_boundary_sample_count=len(field.continuation_boundary),
    result_continuation_boundary_verified=field.continuation_boundary_verified,
    result_topology_verified=bool(
      field.topology.connected
      and field.topology.forms_closed_zone
      and field.topology.nonmanifold_edge_count == 0
    ),
    result_pressure_lineage_verified=field.pressure_lineage_verified,
    result_characteristic_geometry_verified=field.characteristic_geometry_verified,
    result_variable_entropy_compatibility_verified=(
      field.variable_entropy_compatibility_verified
    ),
    result_cell_euler_residuals_verified=field.cell_euler_residuals_verified,
    result_internal_characteristic_closure_verified=(
      field.internal_characteristic_closure_verified
    ),
    result_physical_closure_verified=field.physical_closure_verified,
    result_chain_promotion_blocked=field.chain_promotion_blocked,
    result_production_claim_allowed=field.production_claim_allowed,
  )
  return result(field.as_chain_termination_decision())


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve:
  """One open entropy-characteristic field and the exact frontier it used.

  The frontier is retained beside the returned field because it is a
  solver-to-solver handoff, not a physical ``MocChainCell`` perimeter.  A
  future reflected/free-boundary solver can implement this same contract
  without changing the planner's fidelity ceiling.
  """

  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
  incoming_handoff: tuple[MocChainBoundarySample, ...]

  def __post_init__(self) -> None:
    if not isinstance(
      self.field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'field must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
      )
    handoff = tuple(self.incoming_handoff)
    if not handoff:
      raise ValueError('incoming_handoff must contain state-carrying samples')
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    object.__setattr__(self, 'incoming_handoff', handoff)

  @property
  def outgoing_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the returned field's typed post-shock perimeter."""

    return self.field.continuation_boundary

  def as_report(self) -> dict[str, Any]:
    return {
      'field_status': self.field.status.value,
      'field_converged': self.field.converged,
      'field_local_consistency_verified': (
        self.field.local_consistency_verified
      ),
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_fingerprint': _handoff_fingerprint(
        self.incoming_handoff
      ),
      'outgoing_handoff_kind': self.field.continuation_boundary_kind.value,
      'outgoing_handoff_sample_count': len(self.outgoing_handoff),
      'outgoing_handoff_fingerprint': _handoff_fingerprint(
        self.outgoing_handoff
      ),
      'field_fingerprint': _euler_entropy_characteristic_field_fingerprint(
        self.field
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep:
  """One callback attempt in the open entropy-field sequence."""

  next_field_index: int
  incoming_handoff_sample_count: int
  incoming_handoff_fingerprint: str | None
  incoming_handoff_link_verified: bool
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_field_status: str | None = None
  result_field_fingerprint: str | None = None
  result_continuation_boundary_kind: MocChainBoundaryKind | None = None
  result_continuation_boundary_sample_count: int | None = None
  result_continuation_boundary_verified: bool | None = None
  result_field_local_consistency_verified: bool | None = None
  result_handoff_fingerprint: str | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.next_field_index, bool)
      or not isinstance(self.next_field_index, int)
      or self.next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    if (
      isinstance(self.incoming_handoff_sample_count, bool)
      or not isinstance(self.incoming_handoff_sample_count, int)
      or self.incoming_handoff_sample_count < 0
    ):
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    if not isinstance(self.incoming_handoff_link_verified, bool):
      raise TypeError('incoming_handoff_link_verified must be a bool')
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    for name in (
      'incoming_handoff_fingerprint',
      'result_status',
      'result_field_status',
      'result_field_fingerprint',
      'result_handoff_fingerprint',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if self.result_continuation_boundary_kind is not None and not isinstance(
      self.result_continuation_boundary_kind,
      MocChainBoundaryKind,
    ):
      raise TypeError(
        'result_continuation_boundary_kind must be a '
        'MocChainBoundaryKind or None'
      )
    if self.result_continuation_boundary_sample_count is not None:
      if (
        isinstance(self.result_continuation_boundary_sample_count, bool)
        or not isinstance(self.result_continuation_boundary_sample_count, int)
        or self.result_continuation_boundary_sample_count < 0
      ):
        raise ValueError(
          'result_continuation_boundary_sample_count must be nonnegative'
        )
    for name in (
      'result_continuation_boundary_verified',
      'result_field_local_consistency_verified',
      'result_physical_termination',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, bool):
        raise TypeError(f'{name} must be a bool or None')
    if self.result_termination_reason is not None and not isinstance(
      self.result_termination_reason,
      MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )

  def as_report(self) -> dict[str, Any]:
    return {
      'next_field_index': self.next_field_index,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_field_status': self.result_field_status,
      'result_field_fingerprint': self.result_field_fingerprint,
      'result_continuation_boundary_kind': (
        None
        if self.result_continuation_boundary_kind is None
        else self.result_continuation_boundary_kind.value
      ),
      'result_continuation_boundary_sample_count': (
        self.result_continuation_boundary_sample_count
      ),
      'result_continuation_boundary_verified': (
        self.result_continuation_boundary_verified
      ),
      'result_field_local_consistency_verified': (
        self.result_field_local_consistency_verified
      ),
      'result_handoff_fingerprint': self.result_handoff_fingerprint,
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult:
  """A research-only sequence of locally closed entropy-characteristic fields.

  This result is deliberately not a ``MocChainResult``.  It records exact
  state/pressure frontiers and fresh downstream domains, while the reflected
  free boundary and physical shock-cell perimeter remain unsolved.
  """

  seed: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
  fields: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult, ...]
  steps: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep, ...
  ]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.seed,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'seed must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
      )
    fields = tuple(self.fields)
    if not fields or fields[0] is not self.seed:
      raise ValueError('fields must retain the seed field as their first entry')
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      )
      for value in fields
    ):
      raise TypeError(
        'fields must contain '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult values'
      )
    steps = tuple(self.steps)
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep,
      )
      for value in steps
    ):
      raise TypeError(
        'steps must contain '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep values'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'entropy-characteristic field chains must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'fields', fields)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )

  @property
  def field_count(self) -> int:
    return len(self.fields)

  @property
  def continued_field_count(self) -> int:
    return max(0, len(self.fields) - 1)

  @property
  def resolved(self) -> bool:
    """Whether local field sequence assembly reached a typed no-next stop."""

    return bool(
      self.fields
      and all(
        _euler_entropy_characteristic_field_local_gates_verified(field)
        for field in self.fields
      )
      and self.handoff_links_verified is True
      and self.termination.reason
      is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    )

  @property
  def local_sequence_verified(self) -> bool:
    """Whether every retained field and exact frontier link passed locally."""

    return bool(
      self.fields
      and all(
        _euler_entropy_characteristic_field_local_gates_verified(field)
        for field in self.fields
      )
      and self.handoff_links_verified is True
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def handoff_links_verified(self) -> bool | None:
    if not self.steps:
      return None
    return all(step.incoming_handoff_link_verified for step in self.steps)

  @property
  def physical_chain_cell_count(self) -> int:
    """An open field sequence never manufactures physical chain cells."""

    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'local_sequence_verified': self.local_sequence_verified,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'handoff_links_verified': self.handoff_links_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fields': [field.as_report() for field in self.fields],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock:
  """Deterministic replay fixture for the entropy-field continuation seam.

  The fixture intentionally accepts explicitly supplied future field results;
  it does not translate or synthesize a downstream field.  That keeps the
  missing reflected/free-boundary solve visible instead of turning a geometry
  replay into physical shock-cell evidence.
  """

  next_fields: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult, ...
  ] = ()
  model: str = 'replay-euler-ambient-first-wedge-entropy-characteristic-field-chain-mock'

  def __post_init__(self) -> None:
    fields = tuple(self.next_fields)
    if any(
      not isinstance(
        field,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      )
      for field in fields
    ):
      raise TypeError(
        'next_fields must contain '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult values'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'next_fields', fields)
    object.__setattr__(self, 'model', model)

  @property
  def total_field_count(self) -> int:
    """Return the seed-inclusive replay length."""

    return len(self.next_fields) + 1

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'total_field_count_including_seed': self.total_field_count,
      'explicit_next_field_count': len(self.next_fields),
      'fresh_domain_policy': 'planner-validates-supplied-future-field-domain',
      'incoming_handoff_policy': (
        'exact-post-shock-field-perimeter-replayed; no synthetic downstream-'
        'field-or-physical-shock-cell-is-created'
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'deterministic-explicit-replay-of-euler-entropy-characteristic-fields; '
        'reflected-free-boundary-and-physical-chain-closure-pending'
      ),
    }

  def solve_next(
    self,
    current: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    next_field_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve
    | MocChainTerminationDecision
  ):
    if not isinstance(
      current,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError(
        'current must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
      )
    if (
      isinstance(next_field_index, bool)
      or not isinstance(next_field_index, int)
      or next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    handoff = tuple(incoming_handoff)
    if handoff != current.continuation_boundary:
      raise ValueError(
        'incoming_handoff must exactly match current.continuation_boundary'
      )
    replay_index = next_field_index - 2
    if replay_index >= len(self.next_fields):
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'entropy-characteristic field replay mock exhausted its explicitly '
          f'configured {self.total_field_count}-field sequence'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_field_index': next_field_index,
          'incoming_handoff_sample_count': len(handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
          'synthetic_downstream_field_created': False,
        },
      )
    return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve(
      field=self.next_fields[replay_index],
      incoming_handoff=handoff,
    )


def plan_euler_ambient_first_wedge_entropy_characteristic_field_chain(
  seed: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  solve_next: Callable[
    [
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  total_field_count: int,
  position_tolerance_m: float = 1.0e-10,
  claim_status: str | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult:
  """Continue typed entropy fields without promoting open fields to cells.

  The callback receives the exact ``1 -> 4 -> 2`` post-shock perimeter from
  the currently accepted field.  A returned field must be locally closed,
  carry its own typed perimeter, and occupy a fresh downstream domain.  The
  planner records the sequence only; an independent audit and a future
  reflected/free-boundary solve remain required for physical promotion.
  """

  if not isinstance(
    seed,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    raise TypeError(
      'seed must be a '
      'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
    )
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  if (
    isinstance(total_field_count, bool)
    or not isinstance(total_field_count, int)
    or total_field_count < 1
  ):
    raise ValueError('total_field_count must be a positive integer')
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  fields: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
  ] = [seed]
  steps: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep
  ] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult:
    return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult(
      seed=seed,
      fields=tuple(fields),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'euler-ambient-first-wedge-entropy-characteristic-field-chain; '
        'reflected-free-boundary and physical shock-cell closure pending'
        if claim_status is None
        else claim_status
      ),
      diagnostics={
        'planner_model': (
          'euler-ambient-first-wedge-entropy-characteristic-field-chain'
        ),
        'total_field_count_requested': total_field_count,
        'accepted_field_count': len(fields),
        'continuation_boundary_kind': (
          seed.continuation_boundary_kind.value
        ),
        'continuation_boundary_node_indices': (
          seed.continuation_boundary_node_indices
        ),
        'open_field_promotion_policy': 'never-create-moc-chain-cell',
        'fresh_domain_tolerance_m': tolerance,
        'independent_audit_required': True,
        'physical_chain_cell_count': 0,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  def append_step(
    next_field_index: int,
    incoming: tuple[MocChainBoundarySample, ...],
    **values: Any,
  ) -> None:
    steps.append(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainStep(
        next_field_index=next_field_index,
        incoming_handoff_sample_count=len(incoming),
        incoming_handoff_fingerprint=_handoff_fingerprint(incoming),
        incoming_handoff_link_verified=values.pop(
          'incoming_handoff_link_verified',
          False,
        ),
        **values,
      )
    )

  if not _euler_entropy_characteristic_field_local_gates_verified(seed):
    return result(seed.as_chain_termination_decision())

  for next_field_index in range(2, total_field_count + 2):
    current = fields[-1]
    incoming = current.continuation_boundary
    if not current.continuation_boundary_verified or not incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'accepted entropy-characteristic field has no verified typed '
          'continuation perimeter'
        ),
        diagnostics={
          'current_field_index': len(fields),
          'current_field_fingerprint': (
            _euler_entropy_characteristic_field_fingerprint(current)
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        result_kind='termination-returned',
        result_status='continuation-boundary-failure',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    try:
      solved = solve_next(current, next_field_index, incoming)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'entropy-characteristic field continuation raised: {error}',
        diagnostics={
          'current_field_index': len(fields),
          'current_field_fingerprint': (
            _euler_entropy_characteristic_field_fingerprint(current)
          ),
          'solver_error': type(error).__name__,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='solver-error',
        result_status=type(error).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if solved is None:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'entropy-characteristic field continuation returned no next field'
        ),
        diagnostics={
          'current_field_index': len(fields),
          'current_field_fingerprint': (
            _euler_entropy_characteristic_field_fingerprint(current)
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='none',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if isinstance(solved, MocChainTerminationDecision):
      if solved.physical_termination:
        termination = MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
          message=(
            'an open entropy-characteristic field cannot declare physical '
            'termination before reflected/free-boundary closure'
          ),
          diagnostics={
            **dict(solved.diagnostics),
            'returned_physical_termination': True,
          },
        )
      else:
        termination = solved
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='decision',
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)

    if not isinstance(
      solved,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldContinuationSolve,
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=(
          'entropy-characteristic continuation must return a continuation '
          'solve, typed termination, or None'
        ),
        diagnostics={'returned_type': type(solved).__name__},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='invalid-result-returned',
        result_status=type(solved).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    next_field = solved.field
    fingerprint = _euler_entropy_characteristic_field_fingerprint(next_field)
    if solved.incoming_handoff != incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'entropy-characteristic continuation did not retain the exact '
          'incoming post-shock perimeter'
        ),
        diagnostics={
          'expected_incoming_handoff_fingerprint': _handoff_fingerprint(incoming),
          'returned_incoming_handoff_fingerprint': _handoff_fingerprint(
            solved.incoming_handoff
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=False,
        result_kind='handoff-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if next_field is current:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'entropy-characteristic continuation reused the current field object'
        ),
        diagnostics={'field_fingerprint': fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-reuse-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not next_field.converged:
      termination = next_field.as_chain_termination_decision()
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_continuation_boundary_kind=next_field.continuation_boundary_kind,
        result_continuation_boundary_sample_count=len(
          next_field.continuation_boundary
        ),
        result_continuation_boundary_verified=(
          next_field.continuation_boundary_verified
        ),
        result_field_local_consistency_verified=(
          next_field.local_consistency_verified
        ),
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not _euler_entropy_characteristic_field_local_gates_verified(next_field):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message=(
          'next entropy-characteristic field lacks its complete local '
          'closure and fidelity gates'
        ),
        diagnostics={
          'field_fingerprint': fingerprint,
          'local_consistency_verified': next_field.local_consistency_verified,
          'continuation_boundary_verified': (
            next_field.continuation_boundary_verified
          ),
          'internal_characteristic_closure_verified': (
            next_field.internal_characteristic_closure_verified
          ),
          'physical_closure_verified': next_field.physical_closure_verified,
          'chain_promotion_blocked': next_field.chain_promotion_blocked,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_continuation_boundary_kind=next_field.continuation_boundary_kind,
        result_continuation_boundary_sample_count=len(
          next_field.continuation_boundary
        ),
        result_continuation_boundary_verified=(
          next_field.continuation_boundary_verified
        ),
        result_field_local_consistency_verified=(
          next_field.local_consistency_verified
        ),
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    current_extent = _euler_entropy_characteristic_field_x_extent(current)
    next_extent = _euler_entropy_characteristic_field_x_extent(next_field)
    if (
      current_extent is None
      or next_extent is None
      or next_extent[0] <= current_extent[1] + tolerance
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message=(
          'next entropy-characteristic field does not occupy a fresh '
          'downstream domain; overlap and backtracking are rejected'
        ),
        diagnostics={
          'current_field_x_extent_m': current_extent,
          'next_field_x_extent_m': next_extent,
          'position_tolerance_m': tolerance,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='fresh-domain-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_continuation_boundary_kind=next_field.continuation_boundary_kind,
        result_continuation_boundary_sample_count=len(
          next_field.continuation_boundary
        ),
        result_continuation_boundary_verified=(
          next_field.continuation_boundary_verified
        ),
        result_field_local_consistency_verified=(
          next_field.local_consistency_verified
        ),
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    outgoing = next_field.continuation_boundary
    if not next_field.continuation_boundary_verified or not outgoing:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=(
          'accepted entropy-characteristic field has no verified outgoing '
          'post-shock perimeter'
        ),
        diagnostics={'field_fingerprint': fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_continuation_boundary_kind=next_field.continuation_boundary_kind,
        result_continuation_boundary_sample_count=len(outgoing),
        result_continuation_boundary_verified=(
          next_field.continuation_boundary_verified
        ),
        result_field_local_consistency_verified=(
          next_field.local_consistency_verified
        ),
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    fields.append(next_field)
    append_step(
      next_field_index,
      incoming,
      incoming_handoff_link_verified=True,
      result_kind='field-solve-returned',
      result_status=next_field.status.value,
      result_field_status=next_field.status.value,
      result_field_fingerprint=fingerprint,
      result_continuation_boundary_kind=next_field.continuation_boundary_kind,
      result_continuation_boundary_sample_count=len(outgoing),
      result_continuation_boundary_verified=(
        next_field.continuation_boundary_verified
      ),
      result_field_local_consistency_verified=(
        next_field.local_consistency_verified
      ),
      result_handoff_fingerprint=_handoff_fingerprint(outgoing),
    )

  termination = MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.MAX_CELL_LIMIT,
    message=(
      'entropy-characteristic field chain reached its configured field limit; '
      'physical shock-cell promotion remains blocked'
    ),
    diagnostics={
      'total_field_count': total_field_count,
      'accepted_field_count': len(fields),
    },
  )
  return result(termination)


def plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock(
  seed: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  *,
  mock: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock | None = None,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult:
  """Run the explicit replay fixture for the entropy-field chain seam."""

  fixture = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock()
    if mock is None
    else mock
  )
  if not isinstance(
    fixture,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock,
  ):
    raise TypeError(
      'mock must be a '
      'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock'
    )
  return plan_euler_ambient_first_wedge_entropy_characteristic_field_chain(
    seed,
    fixture.solve_next,
    total_field_count=fixture.total_field_count,
    position_tolerance_m=position_tolerance_m,
    claim_status=(
      'deterministic-explicit-replay-euler-entropy-characteristic-field-chain; '
      'reflected-free-boundary-and-physical-chain-closure-pending'
    ),
  )


def plan_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_probe(
  seed: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  *,
  start_point_m: tuple[float, float] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult:
  """Run one bounded shock attempt through the entropy-field chain seam.

  This is the first non-mock callback path for the entropy-characteristic
  chain.  It consumes the exact perimeter, calls the attached-shock marcher,
  and records the resulting bounded-field stop in the same planner structure
  used by the explicit replay mock.  It never promotes the open field to a
  physical chain cell.
  """

  if not isinstance(
    seed,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    raise TypeError(
      'seed must be a '
      'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult'
    )
  attempt_reports: list[dict[str, Any]] = []

  def solve_next(
    current: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    _next_field_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocChainTerminationDecision:
    resolved_start = (
      current.continuation_boundary[0].point_m
      if start_point_m is None
      else start_point_m
    )
    attempt = solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
      current,
      incoming_handoff,
      resolved_start,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    attempt_report = attempt.as_report()
    attempt_reports.append(attempt_report)
    decision = attempt.as_chain_termination_decision()
    diagnostics = dict(decision.diagnostics)
    diagnostics.update({
      'planner_model': (
        'euler-ambient-first-wedge-entropy-characteristic-field-shock-'
        'coupling-probe'
      ),
      'shock_coupling_attempt': attempt_report,
      'synthetic_downstream_field_created': False,
      'physical_chain_cell_count': 0,
    })
    return replace(decision, diagnostics=diagnostics)

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field_chain(
    seed,
    solve_next,
    total_field_count=1,
    position_tolerance_m=position_tolerance_m,
    claim_status=(
      'solver-generated-bounded-entropy-characteristic-shock-coupling-probe; '
      'reflected-free-boundary-and-physical-chain-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'planner_model': (
      'euler-ambient-first-wedge-entropy-characteristic-field-shock-'
      'coupling-probe'
    ),
    'shock_coupling_attempt_count': len(attempt_reports),
    'shock_coupling_attempts': attempt_reports,
    'synthetic_downstream_field_created': False,
    'physical_chain_cell_count': 0,
  })
  return replace(planner, diagnostics=diagnostics)


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep:
  """One declared entropy-carrying projection resolution in the planner."""

  subdivision_level: int
  subdivision_side_count: int
  result_status: str
  result_kind: str
  result_converged: bool
  result_cell_count: int
  result_state_sample_count: int
  result_maximum_cell_euler_residual: float | None
  result_topology_verified: bool
  result_state_projection_verified: bool
  result_pressure_lineage_carried: bool
  result_cell_euler_residuals_finite: bool
  result_cell_euler_residuals_verified: bool
  result_internal_characteristic_closure_verified: bool
  result_physical_closure_verified: bool
  result_chain_promotion_blocked: bool
  result_production_claim_allowed: bool

  def __post_init__(self) -> None:
    for name in ('subdivision_level', 'subdivision_side_count', 'result_cell_count', 'result_state_sample_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in ('result_status', 'result_kind'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    if self.result_maximum_cell_euler_residual is not None:
      value = float(self.result_maximum_cell_euler_residual)
      if not isfinite(value) or value < 0.0:
        raise ValueError(
          'result_maximum_cell_euler_residual must be finite and nonnegative'
        )
      object.__setattr__(self, 'result_maximum_cell_euler_residual', value)
    for name in (
      'result_converged',
      'result_topology_verified',
      'result_state_projection_verified',
      'result_pressure_lineage_carried',
      'result_cell_euler_residuals_finite',
      'result_cell_euler_residuals_verified',
      'result_internal_characteristic_closure_verified',
      'result_physical_closure_verified',
      'result_chain_promotion_blocked',
      'result_production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.result_internal_characteristic_closure_verified:
      raise ValueError(
        'projection refinement planner steps cannot claim internal characteristic closure'
      )
    if self.result_physical_closure_verified:
      raise ValueError(
        'projection refinement planner steps cannot claim physical closure'
      )
    if self.result_production_claim_allowed:
      raise ValueError(
        'projection refinement planner steps cannot claim production validity'
      )

  def as_report(self) -> dict[str, Any]:
    return {
      'subdivision_level': self.subdivision_level,
      'subdivision_side_count': self.subdivision_side_count,
      'result_status': self.result_status,
      'result_kind': self.result_kind,
      'result_converged': self.result_converged,
      'result_cell_count': self.result_cell_count,
      'result_state_sample_count': self.result_state_sample_count,
      'result_maximum_cell_euler_residual': self.result_maximum_cell_euler_residual,
      'checks': {
        'topology_verified': self.result_topology_verified,
        'state_projection_verified': self.result_state_projection_verified,
        'pressure_lineage_carried': self.result_pressure_lineage_carried,
        'cell_euler_residuals_finite': self.result_cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.result_cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerResult:
  """An entropy-carrying resolution ladder with a hard pre-chain stop."""

  seed: MocEulerAmbientFirstWedgeCharacteristicResult
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None
  refinements: tuple[MocEulerAmbientFirstWedgeEntropyCarryRefinementResult, ...]
  steps: tuple[MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep, ...]
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(
      self.seed,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError(
        'seed must be a MocEulerAmbientFirstWedgeCharacteristicResult'
      )
    if self.entropy_carry is not None and not isinstance(
      self.entropy_carry,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError(
        'entropy_carry must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryResult or None'
      )
    refinements = tuple(self.refinements)
    steps = tuple(self.steps)
    if len(refinements) != len(steps):
      raise ValueError('refinements and steps must have equal lengths')
    if any(
      not isinstance(
        refinement,
        MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
      )
      for refinement in refinements
    ):
      raise TypeError(
        'refinements must contain '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementResult values'
      )
    if any(
      not isinstance(
        step,
        MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep,
      )
      for step in steps
    ):
      raise TypeError(
        'steps must contain '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep values'
      )
    object.__setattr__(self, 'refinements', refinements)
    object.__setattr__(self, 'steps', steps)
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError('termination must be a MocChainTerminationDecision')
    if self.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH:
      raise ValueError(
        'entropy-carrying refinement planner must use the upstream-coupled '
        'research planner kind'
      )
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )

  @property
  def attempted(self) -> bool:
    return self.entropy_carry is not None

  @property
  def resolved(self) -> bool:
    return bool(
      self.entropy_carry is not None
      and self.refinements
      and self.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'claim_status': self.claim_status,
      'attempted': self.attempted,
      'resolved': self.resolved,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'entropy_carry': (
        None
        if self.entropy_carry is None
        else self.entropy_carry.as_report()
      ),
      'refinements': [refinement.as_report() for refinement in self.refinements],
      'steps': [step.as_report() for step in self.steps],
      'termination': self.termination.as_report(),
      'diagnostics': dict(self.diagnostics),
    }


def plan_euler_ambient_first_wedge_entropy_carry_refinement(
  seed: MocEulerAmbientFirstWedgeCharacteristicResult,
  *,
  subdivision_levels: Sequence[int] = (1, 2, 3),
  position_tolerance_m: float = 1.0e-10,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  maximum_iterations: int = 24,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerResult:
  """Plan a bounded entropy-carrying projection ladder without chain cells."""

  if not isinstance(seed, MocEulerAmbientFirstWedgeCharacteristicResult):
    raise TypeError(
      'seed must be a MocEulerAmbientFirstWedgeCharacteristicResult'
    )
  try:
    levels = tuple(subdivision_levels)
  except TypeError as error:
    raise ValueError('subdivision_levels must be an iterable of integers') from error
  if not levels or any(
    isinstance(level, bool) or not isinstance(level, int) or level < 1
    for level in levels
  ):
    raise ValueError('subdivision_levels must contain positive integers')
  if any(right <= left for left, right in zip(levels, levels[1:])):
    raise ValueError('subdivision_levels must be strictly increasing')
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None = None
  refinements: list[MocEulerAmbientFirstWedgeEntropyCarryRefinementResult] = []
  steps: list[MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerResult:
    return MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerResult(
      seed=seed,
      entropy_carry=entropy_carry,
      refinements=tuple(refinements),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'solver-owned-entropy-carrying-refinement-planner; projected '
        'residual reduction does not establish internal characteristic closure '
        'or authorize a continued physical shock-cell chain'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-entropy-carry-refinement',
        'subdivision_levels': levels,
        'refinement_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'independent_ladder_audit_required': True,
      },
    )

  try:
    entropy_carry = solve_euler_ambient_first_wedge_entropy_carry(
      seed,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      edge_alignment_tolerance=edge_alignment_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      maximum_iterations=maximum_iterations,
    )
    for level in levels:
      refinement = refine_euler_ambient_first_wedge_entropy_carry(
        entropy_carry,
        subdivision_level=level,
        position_tolerance_m=position_tolerance_m,
        pressure_lineage_tolerance=pressure_lineage_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
      )
      refinements.append(refinement)
      steps.append(
        MocEulerAmbientFirstWedgeEntropyCarryRefinementPlannerStep(
          subdivision_level=level,
          subdivision_side_count=refinement.subdivision_side_count,
          result_status=refinement.status.value,
          result_kind='solver-owned-entropy-carrying-subcell-projection',
          result_converged=refinement.converged,
          result_cell_count=refinement.cell_count,
          result_state_sample_count=refinement.state_sample_count,
          result_maximum_cell_euler_residual=(
            refinement.maximum_cell_euler_residual
          ),
          result_topology_verified=(
            refinement.topology.connected
            and refinement.topology.forms_closed_zone
            and refinement.topology.nonmanifold_edge_count == 0
          ),
          result_state_projection_verified=refinement.state_projection_verified,
          result_pressure_lineage_carried=refinement.pressure_lineage_carried,
          result_cell_euler_residuals_finite=(
            refinement.cell_euler_residuals_finite
          ),
          result_cell_euler_residuals_verified=(
            refinement.cell_euler_residuals_verified
          ),
          result_internal_characteristic_closure_verified=(
            refinement.internal_characteristic_closure_verified
          ),
          result_physical_closure_verified=refinement.physical_closure_verified,
          result_chain_promotion_blocked=refinement.chain_promotion_blocked,
          result_production_claim_allowed=refinement.production_claim_allowed,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'entropy-carrying refinement planner raised: {error}',
        diagnostics={
          'planner_model': 'euler-ambient-first-wedge-entropy-carry-refinement',
          'solver_error': type(error).__name__,
          'refinement_consumed_as_chain_cell': False,
          'physical_chain_cell_count': 0,
        },
      )
    )
  return result(
    MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
      message=(
        'entropy-carrying subcell projection ladder is retained as residual '
        'evidence; internal characteristic closure, reflected free-boundary '
        'coupling, and external validation still block chain promotion'
      ),
      diagnostics={
        'planner_model': 'euler-ambient-first-wedge-entropy-carry-refinement',
        'refinement_consumed_as_chain_cell': False,
        'physical_chain_cell_count': 0,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'internal-characteristic-family-closure-on-refined-entropy-field-'
          'and-reflected-free-boundary-coupling'
        ),
      },
    )
  )


@dataclass(frozen=True, slots=True)
class MocEulerPostShockFieldChainMock:
  """Deterministic translated local-field sequence fixture.

  Each next field is freshly reassembled from a translated exact shock.  The
  mock exercises state-carrying frontiers and downstream domain separation;
  it never converts a local topological closure into a physical shock cell.
  """

  total_field_count: int = 3
  axial_translation_m: float = 2.0
  model: str = 'translated-euler-local-post-shock-field-chain-mock'

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_field_count, bool)
      or not isinstance(self.total_field_count, int)
      or self.total_field_count < 1
    ):
      raise ValueError('total_field_count must be a positive integer')
    translation = float(self.axial_translation_m)
    if not isfinite(translation) or translation <= 0.0:
      raise ValueError('axial_translation_m must be finite and positive')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'axial_translation_m', translation)
    object.__setattr__(self, 'model', model)

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'planning_only': True,
      'total_field_count_including_seed': self.total_field_count,
      'axial_translation_m': self.axial_translation_m,
      'fresh_domain_policy': (
        'translated-x-domain-reassembled-by-local-euler-post-shock-solver'
      ),
      'incoming_handoff_policy': (
        'centerline-frontier-recorded-exactly; ambient-free-boundary-is-not-'
        'inferred'
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'deterministic-local-euler-post-shock-field-sequence-mock; '
        'ambient-free-boundary-and-physical-chain-closure-pending'
      ),
    }

  def solve_next(
    self,
    current: MocEulerPostShockFieldResult,
    next_field_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocEulerPostShockFieldContinuationSolve | MocChainTerminationDecision:
    if not isinstance(current, MocEulerPostShockFieldResult):
      raise TypeError('current must be a MocEulerPostShockFieldResult')
    if (
      isinstance(next_field_index, bool)
      or not isinstance(next_field_index, int)
      or next_field_index < 2
    ):
      raise ValueError('next_field_index must be an integer of at least two')
    handoff = tuple(incoming_handoff)
    if handoff != current.downstream_handoff:
      raise ValueError(
        'incoming_handoff must exactly match current.downstream_handoff'
      )
    if next_field_index > self.total_field_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'local post-shock field chain mock exhausted its configured '
          f'{self.total_field_count}-field sequence'
        ),
        diagnostics={
          'continuation_model': self.model,
          'next_field_index': next_field_index,
          'incoming_handoff_sample_count': len(handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
        },
      )
    if not current.converged:
      return current.as_chain_termination_decision()
    translated = _translate_euler_post_shock_field(
      current,
      self.axial_translation_m,
    )
    return MocEulerPostShockFieldContinuationSolve(
      field=translated,
      incoming_handoff=handoff,
    )


def plan_euler_post_shock_field_chain(
  seed: MocEulerPostShockFieldResult,
  solve_next: Callable[
    [
      MocEulerPostShockFieldResult,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocEulerPostShockFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  total_field_count: int,
  position_tolerance_m: float = 1.0e-10,
  claim_status: str | None = None,
) -> MocEulerPostShockFieldChainPlannerResult:
  """Continue local fields while keeping the physical fidelity ceiling."""

  if not isinstance(seed, MocEulerPostShockFieldResult):
    raise TypeError('seed must be a MocEulerPostShockFieldResult')
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  if (
    isinstance(total_field_count, bool)
    or not isinstance(total_field_count, int)
    or total_field_count < 1
  ):
    raise ValueError('total_field_count must be a positive integer')
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  fields: list[MocEulerPostShockFieldResult] = [seed]
  steps: list[MocEulerPostShockFieldChainStep] = []

  def result(
    termination: MocChainTerminationDecision,
  ) -> MocEulerPostShockFieldChainPlannerResult:
    return MocEulerPostShockFieldChainPlannerResult(
      seed=seed,
      fields=tuple(fields),
      steps=tuple(steps),
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=(
        'euler-local-post-shock-field-chain; ambient/free-boundary closure '
        'and physical shock-cell promotion pending'
        if claim_status is None
        else claim_status
      ),
      diagnostics={
        'planner_model': 'euler-local-post-shock-field-chain',
        'total_field_count_requested': total_field_count,
        'accepted_field_count': len(fields),
        'local_field_promotion_policy': 'never-create-moc-chain-cell',
        'fresh_domain_tolerance_m': tolerance,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  if not seed.converged:
    return result(seed.as_chain_termination_decision())
  if not seed.state_sampling_available:
    return result(
      MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='local post-shock seed has no state-carrying centerline frontier',
        diagnostics={
          'seed_field_status': seed.status.value,
          'seed_field_fingerprint': _euler_post_shock_field_fingerprint(seed),
        },
      )
    )

  def append_step(
    next_field_index: int,
    incoming: tuple[MocChainBoundarySample, ...],
    **values: Any,
  ) -> None:
    steps.append(
      MocEulerPostShockFieldChainStep(
        next_field_index=next_field_index,
        incoming_handoff_sample_count=len(incoming),
        incoming_handoff_fingerprint=_handoff_fingerprint(incoming),
        incoming_handoff_link_verified=values.pop(
          'incoming_handoff_link_verified',
          False,
        ),
        **values,
      )
    )

  for next_field_index in range(2, total_field_count + 2):
    current = fields[-1]
    incoming = current.downstream_handoff
    if not incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='local post-shock field has no outgoing frontier',
        diagnostics={'current_field_index': len(fields)},
      )
      append_step(
        next_field_index,
        incoming,
        result_kind='termination-returned',
        result_status='state-boundary',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    try:
      solved = solve_next(current, next_field_index, incoming)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'local post-shock field continuation raised: {error}',
        diagnostics={
          'current_field_index': len(fields),
          'solver_error': type(error).__name__,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='solver-error',
        result_status=type(error).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if solved is None:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='local post-shock field continuation returned no next field',
        diagnostics={'current_field_index': len(fields)},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='none',
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    if isinstance(solved, MocChainTerminationDecision):
      if solved.physical_termination:
        termination = MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
          message=(
            'a local post-shock topology cannot declare physical termination '
            'before ambient/free-boundary closure'
          ),
          diagnostics={
            **dict(solved.diagnostics),
            'returned_physical_termination': True,
          },
        )
      else:
        termination = solved
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='termination-returned',
        result_status='decision',
        result_termination_reason=termination.reason,
        result_physical_termination=termination.physical_termination,
      )
      return result(termination)

    if not isinstance(solved, MocEulerPostShockFieldContinuationSolve):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message=(
          'local post-shock field continuation must return a continuation '
          'solve, typed termination, or None'
        ),
        diagnostics={'returned_type': type(solved).__name__},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='invalid-result-returned',
        result_status=type(solved).__name__,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    next_field = solved.field
    fingerprint = _euler_post_shock_field_fingerprint(next_field)
    if solved.incoming_handoff != incoming:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='local post-shock continuation did not retain the exact frontier',
        diagnostics={
          'expected_incoming_handoff_fingerprint': _handoff_fingerprint(incoming),
          'returned_incoming_handoff_fingerprint': _handoff_fingerprint(
            solved.incoming_handoff
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=False,
        result_kind='handoff-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if next_field is current:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='local post-shock continuation reused the current field object',
        diagnostics={'field_fingerprint': fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-reuse-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not next_field.converged:
      termination = next_field.as_chain_termination_decision()
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    if not (
      next_field.closed_topology_verified
      and next_field.uniform_state_verified
      and next_field.characteristic_geometry_verified
      and next_field.state_sampling_available
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message='next local post-shock field lacks its local evidence gates',
        diagnostics={
          'field_fingerprint': fingerprint,
          'closed_topology_verified': next_field.closed_topology_verified,
          'uniform_state_verified': next_field.uniform_state_verified,
          'characteristic_geometry_verified': (
            next_field.characteristic_geometry_verified
          ),
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)

    current_extent = _euler_post_shock_field_x_extent(current)
    next_extent = _euler_post_shock_field_x_extent(next_field)
    if (
      current_extent is None
      or next_extent is None
      or next_extent[0] <= current_extent[1] + tolerance
    ):
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        message='next local post-shock field does not occupy a fresh domain',
        diagnostics={
          'current_field_x_extent_m': current_extent,
          'next_field_x_extent_m': next_extent,
          'position_tolerance_m': tolerance,
        },
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='fresh-domain-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    outgoing = next_field.downstream_handoff
    if not outgoing:
      termination = MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message='accepted local post-shock field has no outgoing frontier',
        diagnostics={'field_fingerprint': fingerprint},
      )
      append_step(
        next_field_index,
        incoming,
        incoming_handoff_link_verified=True,
        result_kind='field-rejected',
        result_status=next_field.status.value,
        result_field_status=next_field.status.value,
        result_field_fingerprint=fingerprint,
        result_termination_reason=termination.reason,
        result_physical_termination=False,
      )
      return result(termination)
    fields.append(next_field)
    append_step(
      next_field_index,
      incoming,
      incoming_handoff_link_verified=True,
      result_kind='field-solve-returned',
      result_status=next_field.status.value,
      result_field_status=next_field.status.value,
      result_field_fingerprint=fingerprint,
      result_handoff_sample_count=len(outgoing),
      result_handoff_fingerprint=_handoff_fingerprint(outgoing),
    )

  termination = MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.MAX_CELL_LIMIT,
    message='local post-shock field chain reached its configured field limit',
    diagnostics={'total_field_count': total_field_count},
  )
  return result(termination)


def plan_euler_post_shock_field_chain_mock(
  seed: MocEulerPostShockFieldResult,
  *,
  mock: MocEulerPostShockFieldChainMock | None = None,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerPostShockFieldChainPlannerResult:
  """Run the deterministic translated local-field sequence fixture."""

  fixture = MocEulerPostShockFieldChainMock() if mock is None else mock
  if not isinstance(fixture, MocEulerPostShockFieldChainMock):
    raise TypeError('mock must be a MocEulerPostShockFieldChainMock')
  return plan_euler_post_shock_field_chain(
    seed,
    fixture.solve_next,
    total_field_count=fixture.total_field_count,
    position_tolerance_m=position_tolerance_m,
    claim_status=(
      'deterministic-euler-local-post-shock-field-chain-mock; ambient-free-'
      'boundary closure and physical shock-cell promotion pending'
    ),
  )
  ####


def plan_post_shock_field_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a chain whose next shock consumes the prior solved field.

  ``start_point_at`` chooses each new shock start from the current field and
  cell.  The default endpoint advances by the initial seed-cell axial length;
  ``end_x_at`` may supply a different solver-owned endpoint.  The prior field
  is replaced only after a complete field-coupled next-cell solve returns, so
  an upstream-domain miss or typed terminal cannot be converted into a
  prescribed planner cell.

  This is an upstream-coupled research planner.  It is not the prescribed
  boundary mock and remains below the production claim ceiling until the
  downstream boundary and external validation gates are complete.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      start_point_m=start_point,
      end_x_m=next_end_x,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-post-shock-field-coupled-planner; '
      'production-shock-boundary-and-external-validation-pending'
    ),
  )
####


def plan_source_strip_shock_chain(
  seed: MocPostShockCharacteristicFieldResult,
  source_continuation: MocSourceStripContinuationResult,
  *,
  start_point_m: tuple[float, float],
  start_x_m: float,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one shock-cell step from a bounded source-strip continuation.

  A source strip supplies upstream state and pressure samples for one new
  shock attempt.  It is not reused as though it were a downstream chain
  field: a successful first attempt may produce one new field, after which
  the planner returns an explicit non-physical one-step-domain stop.  A
  source-strip caustic is preserved as a typed characteristic stop before
  the shock solver is called.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(source_continuation, MocSourceStripContinuationResult):
    raise TypeError(
      'source_continuation must be a MocSourceStripContinuationResult'
    )
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  source_strip = source_continuation.strip
  if source_continuation.converged and source_strip is not None and source_strip.converged:
    initial_decision: MocChainTerminationDecision | None = None
  elif (
    source_continuation.remesh is not None
    and source_continuation.remesh.chain_termination_available
  ):
    source_strip = None
    initial_decision = source_continuation.remesh.as_chain_termination_decision()
  else:
    source_strip = None
    initial_decision = MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'source-strip continuation did not provide a converged bounded '
        'upstream field for a next shock-cell attempt'
      ),
      diagnostics={
        'termination_model': 'source-strip-continuation-boundary',
        'upstream_field_model': 'bounded-source-characteristic-strip-continuation',
        'source_continuation_status': source_continuation.status.value,
        'source_continuation_message': source_continuation.message,
        'last_converged_strip': (
          None
          if source_continuation.last_converged_strip is None
          else source_continuation.last_converged_strip.as_report()
        ),
      },
    )

  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'source-strip shock planner completed its one-step upstream '
          'domain; a later cell requires a newly solved bounded upstream field'
        ),
        diagnostics={
          'termination_model': 'bounded-source-strip-one-step-domain',
          'upstream_field_model': 'bounded-source-characteristic-strip',
          'source_strip_reuse_policy': 'never-reuse-after-one-next-cell-attempt',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    if initial_decision is not None:
      return initial_decision
    assert source_strip is not None
    solved = solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      start_point_m=start_point_m,
      end_x_m=current.end_x_m + cell_axial_length_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-source-strip-shock-chain-planner; '
      'one-step-domain; caustic-or-downstream-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'source_strip_continuation': source_continuation.as_report(),
    'source_strip_chain_model': 'bounded-source-strip-one-step',
    'one_step_domain': True,
    'source_strip_reuse_policy': 'never-reuse-after-one-next-cell-attempt',
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_source_strip_shock_chain_sequence(
  seed: MocPostShockCharacteristicFieldResult,
  source_continuation: MocSourceStripContinuationResult,
  source_continuation_at: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocSourceStripContinuationResult | MocChainTerminationDecision | None,
  ],
  *,
  start_point_at: Callable[
    [MocChainCell, int, MocSourceStripContinuationResult],
    tuple[float, float],
  ],
  start_x_m: float,
  end_x_m: float,
  end_x_at: Callable[
    [MocChainCell, int, MocSourceStripContinuationResult],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a chain with a newly solved bounded source field per cell.

  ``source_continuation`` supplies the first next-shock attempt.  After a
  successful cell, ``source_continuation_at`` must return a distinct,
  converged source-strip continuation for the next attempt.  The planner
  rejects reuse of either the continuation result or its strip object, and a
  missing/nonconverged source domain becomes a typed upstream-field boundary.
  This keeps a finite source strip from being mistaken for a downstream chain
  field or silently reused outside its solved domain.

  The sequence remains a solver-generated research planner.  It does not
  provide the physical reflected-field or mixed-regime downstream closure
  required for product promotion.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(source_continuation, MocSourceStripContinuationResult):
    raise TypeError(
      'source_continuation must be a MocSourceStripContinuationResult'
    )
  if not callable(source_continuation_at):
    raise TypeError('source_continuation_at must be callable')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  source_history: list[MocSourceStripContinuationResult] = [
    source_continuation,
  ]
  used_continuation_ids = {id(source_continuation)}
  used_strip_ids = (
    {id(source_continuation.strip)}
    if source_continuation.strip is not None
    else set()
  )
  initial_strip_fingerprint = _source_strip_fingerprint(source_continuation)
  used_strip_fingerprints = (
    {initial_strip_fingerprint}
    if initial_strip_fingerprint is not None
    else set()
  )
  source_attempts: list[dict[str, Any]] = [{
    'current_cell_index': 1,
    'next_cell_index': 2,
    'role': 'initial-source-continuation',
    'continuation': source_continuation.as_report(),
    'fresh_continuation': True,
    'fresh_strip': source_continuation.strip is not None,
    'source_strip_fingerprint': initial_strip_fingerprint,
  }]

  def continuation_stop(
    continuation: MocSourceStripContinuationResult,
    next_cell_index: int,
    *,
    message: str | None = None,
    policy_label: str = 'fresh-bounded-source-strip-required-per-cell',
    allow_remesh_decision: bool = True,
  ) -> MocChainTerminationDecision:
    if (
      allow_remesh_decision
      and
      continuation.remesh is not None
      and continuation.remesh.chain_termination_available
    ):
      remesh_decision = continuation.remesh.as_chain_termination_decision()
      diagnostics = dict(remesh_decision.diagnostics)
      diagnostics.update({
        'source_continuation_status': continuation.status.value,
        'source_continuation_message': continuation.message,
        'next_cell_index': next_cell_index,
        'source_strip_reuse_policy': policy_label,
      })
      return replace(remesh_decision, diagnostics=diagnostics)
    stop_message = message if message is not None else continuation.message
    if not stop_message:
      stop_message = (
        'source-strip continuation did not provide a converged bounded '
        'upstream field for the next shock-cell attempt'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=stop_message,
      diagnostics={
        'termination_model': 'bounded-source-characteristic-strip-sequence',
        'upstream_field_model': 'bounded-source-characteristic-strip',
        'source_continuation_status': continuation.status.value,
        'source_continuation_message': continuation.message,
        'last_converged_strip': (
          None
          if continuation.last_converged_strip is None
          else continuation.last_converged_strip.as_report()
        ),
        'next_cell_index': next_cell_index,
        'source_strip_reuse_policy': policy_label,
      },
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    if next_cell_index == 2:
      next_source: (
        MocSourceStripContinuationResult
        | MocChainTerminationDecision
        | None
      ) = source_continuation
    else:
      next_source = source_continuation_at(
        current,
        next_cell_index,
        incoming_handoff,
      )
      if next_source is None:
        source_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'source-continuation-provider',
          'provider_result': None,
          'fresh_continuation': False,
          'fresh_strip': False,
        })
        return MocChainTerminationDecision(
          physical_termination=False,
          reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
          message=(
            'source-continuation provider returned no bounded upstream field '
            'for the next shock-cell attempt'
          ),
          diagnostics={
            'termination_model': 'bounded-source-characteristic-strip-sequence',
            'upstream_field_model': 'bounded-source-characteristic-strip',
            'next_cell_index': next_cell_index,
            'source_strip_reuse_policy': (
              'fresh-bounded-source-strip-required-per-cell'
            ),
          },
        )
      if isinstance(next_source, MocChainTerminationDecision):
        source_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'source-continuation-provider',
          'provider_decision': next_source.as_report(),
          'fresh_continuation': False,
          'fresh_strip': False,
        })
        if next_source.physical_termination:
          return MocChainTerminationDecision(
            physical_termination=False,
            reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
            message=(
              'source-continuation provider cannot declare physical plume '
              'termination from an upstream domain boundary'
            ),
            diagnostics={
              'termination_model': 'source-provider-physical-stop-rejected',
              'upstream_field_model': 'bounded-source-characteristic-strip',
              'next_cell_index': next_cell_index,
              'source_provider_decision': next_source.as_report(),
            },
          )
        return next_source
      if not isinstance(next_source, MocSourceStripContinuationResult):
        raise TypeError(
          'source_continuation_at must return a '
          'MocSourceStripContinuationResult, MocChainTerminationDecision, or None'
      )
      fresh_continuation = id(next_source) not in used_continuation_ids
      next_strip_fingerprint = _source_strip_fingerprint(next_source)
      source_strip_reused = (
        next_source.strip is not None
        and (
          id(next_source.strip) in used_strip_ids
          or next_strip_fingerprint is None
          or next_strip_fingerprint in used_strip_fingerprints
        )
      )
      strip_is_fresh = next_source.strip is not None and not source_strip_reused
      fresh_strip = strip_is_fresh
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'source-continuation-provider',
        'continuation': next_source.as_report(),
        'fresh_continuation': fresh_continuation,
        'fresh_strip': fresh_strip,
        'source_strip_fingerprint': next_strip_fingerprint,
      })
      if not fresh_continuation or (
        next_source.strip is not None and source_strip_reused
      ):
        return continuation_stop(
          next_source,
          next_cell_index,
          message=(
            'source-continuation provider reused a prior continuation or '
            'source strip; a new bounded upstream field is required for each '
            'continued shock cell'
          ),
          policy_label='reject-reused-source-continuation-or-strip',
          allow_remesh_decision=False,
        )
      source_history.append(next_source)
      used_continuation_ids.add(id(next_source))
      if next_source.strip is not None:
        used_strip_ids.add(id(next_source.strip))
        if next_strip_fingerprint is not None:
          used_strip_fingerprints.add(next_strip_fingerprint)

    if not isinstance(next_source, MocSourceStripContinuationResult):
      raise TypeError('source-continuation sequence selected an invalid source result')
    if (
      not next_source.converged
      or next_source.strip is None
      or not next_source.strip.converged
    ):
      return continuation_stop(next_source, next_cell_index)
    source_strip = next_source.strip
    start_point = start_point_at(current, next_cell_index, next_source)
    next_end_x = (
      end_x_at(current, next_cell_index, next_source)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    return solve_marched_attached_shock_chain_cell_from_source_strip_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      start_point_m=start_point,
      end_x_m=next_end_x,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )

  planner = plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'solver-generated-source-strip-shock-chain-sequence; '
      'fresh-bounded-upstream-domain-per-cell; physical-closure-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'source_strip_chain_model': 'bounded-source-strip-fresh-domain-sequence',
    'one_step_domain': False,
    'source_strip_reuse_policy': (
      'fresh-bounded-source-strip-required-per-cell'
    ),
    'source_domain_count': len(source_history),
    'source_domain_attempt_count': len(source_attempts),
    'source_domain_attempts': source_attempts,
  })
  return replace(planner, diagnostics=diagnostics)
####


def _reflected_domain_source_continuation(
  remesh: MocReflectedDomainRemeshResult,
) -> MocSourceStripContinuationResult:
  """Adapt one reflected-domain result to the generic source-chain lane."""

  if remesh.state_sampling_available:
    return remesh.as_source_continuation()
  request = remesh.request
  plus = () if request is None else request.centerline_source_states
  minus = () if request is None else request.outer_source_states
  return MocSourceStripContinuationResult(
    status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
    strip=None,
    plus_source_states=plus,
    minus_source_states=minus,
    added_sample_count=0,
    axis_step_m=None,
    continuation_k_plus=None,
    message=(
      remesh.message
      or 'reflected-domain remesh did not provide a converged bounded source field'
    ),
    continuation_law=(
      'explicit-reflected-domain-cauchy-remesh'
      if request is None
      else request.source_model
    ),
  )
####


def plan_reflected_domain_remesh_shock_chain(
  seed: MocPostShockCharacteristicFieldResult,
  remesh: MocReflectedDomainRemeshResult,
  *,
  start_point_m: tuple[float, float],
  start_x_m: float,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one shock attempt from an explicit reflected-domain remesh.

  The remesh is adapted to the existing bounded-source planner for one
  attempt only.  A successful shock/field result may become a research cell;
  it does not make the reflected-domain source field a canonical physical
  closure and it cannot be reused for another cell.
  """

  if not isinstance(remesh, MocReflectedDomainRemeshResult):
    raise TypeError('remesh must be a MocReflectedDomainRemeshResult')
  continuation = _reflected_domain_source_continuation(remesh)
  planner = plan_source_strip_shock_chain(
    seed,
    continuation,
    start_point_m=start_point_m,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'reflected_domain_remesh': remesh.as_report(),
    'reflected_domain_chain_model': 'bounded-reflected-domain-remesh-one-step',
    'one_step_domain': True,
    'reflected_domain_reuse_policy': (
      'never-reuse-after-one-next-cell-attempt'
    ),
    'canonical_reflected_domain_closed': False,
    'physical_closure_pending': True,
  })
  return replace(
    planner,
    claim_status=(
      'reflected-domain-remesh shock-chain planner; one-step bounded source; '
      'canonical free-boundary and physical closure pending'
    ),
    diagnostics=diagnostics,
  )
####


def plan_reflected_domain_alternating_source_chain(
  seed: MocPhysicalPostShockFieldResult,
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  start_x_m: float,
  end_x_m: float,
  compression_amplitude_rad: float,
  outer_source_index: int = 0,
  use_outer_seed_attachment: bool = False,
  use_trace_referenced_profile: bool = False,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  attachment_angle_half_width_rad: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one continued cell from an alternating reflected source band.

  The source band is consumed once as a bounded upstream domain.  The local
  physical-field solve receives the exact prior cell handoff and records it
  on the returned field before the ambient-closed physical chain contract
  checks the new cell.  A second callback is an explicit non-physical stop: a
  later cell needs a newly solved alternating source band rather than reuse of
  this finite band.

  ``use_outer_seed_attachment`` opts into attaching the generated shock at
  the retained outgoing reflection-interface seed.  It is intended for a
  fresh reflected-domain continuation; the default attaches at the first
  newly generated outer source row and preserves the original one-step
  behavior.

  ``use_trace_referenced_profile`` is a separate explicit research option.
  It uses the exact retained reflected trace for the downstream turn law and
  requires ``use_outer_seed_attachment``.  It is not enabled by default
  because a trace-profile field can close at one resolution without exposing
  a usable terminal trace for the next remesh.

  The generated shock field is eligible for the research chain lane only
  after its physical-field gates pass.  The planner remains non-production
  because the compression envelope is not the canonical reflected-plume
  free-boundary law.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(
    source_band,
    MocReflectedDomainAlternatingSourceResult,
  ):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if not isinstance(use_outer_seed_attachment, bool):
    raise ValueError('use_outer_seed_attachment must be a bool')
  if not isinstance(use_trace_referenced_profile, bool):
    raise ValueError('use_trace_referenced_profile must be a bool')
  if use_trace_referenced_profile and not use_outer_seed_attachment:
    raise ValueError(
      'use_trace_referenced_profile requires use_outer_seed_attachment'
    )
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  initial_decision: MocChainTerminationDecision | None = None
  if not source_band.source_field_verified:
    initial_decision = MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'alternating reflected source band is not a verified bounded upstream '
        'field; no physical shock-cell attempt was made'
      ),
      diagnostics={
        'termination_model': 'alternating-reflected-source-band',
        'source_band_status': source_band.status.value,
        'source_band': source_band.as_report(),
      },
    )

  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'alternating reflected source planner consumed its bounded source '
          'band for one next cell; a later cell requires a fresh source solve'
        ),
        diagnostics={
          'termination_model': 'alternating-reflected-source-one-step-domain',
          'source_reuse_policy': 'never-reuse-after-one-next-cell-attempt',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    if initial_decision is not None:
      return initial_decision

    solved = solve_reflected_domain_alternating_physical_field(
      source_band,
      compression_amplitude_rad,
      outer_source_index=outer_source_index,
      use_outer_seed_attachment=use_outer_seed_attachment,
      use_trace_referenced_profile=use_trace_referenced_profile,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      attachment_angle_half_width_rad=attachment_angle_half_width_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      incoming_handoff=incoming_handoff,
    )
    if (
      solved.converged
      and solved.field is not None
      and solved.field.converged
      and solved.field.upstream_shock_coupling_verified
    ):
      return MocPhysicalPostShockFieldContinuationSolve(
        field=solved.field,
        end_x_m=current.end_x_m + cell_axial_length_m,
      )

    if solved.status is MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif solved.status is MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'alternating reflected source physical-field solve did not produce '
        f'a chain cell: {solved.message}'
      ),
      diagnostics={
        'termination_model': 'alternating-reflected-source-physical-field',
        'source_band': source_band.as_report(),
        'physical_field': solved.as_report(),
        'next_cell_index': next_cell_index,
      },
    )

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'alternating-reflected-source physical shock-chain planner; bounded '
      'one-step research continuation; canonical free-boundary validation '
      'and production promotion pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'alternating_source_band': source_band.as_report(),
    'alternating_source_chain_model': (
      'bounded-alternating-source-one-step-physical-field'
    ),
    'one_step_domain': True,
    'use_outer_seed_attachment': use_outer_seed_attachment,
    'use_trace_referenced_profile': use_trace_referenced_profile,
    'alternating_source_reuse_policy': (
      'never-reuse-after-one-next-cell-attempt'
    ),
    'canonical_reflected_domain_closed': False,
    'physical_closure_pending': True,
    'canonical_free_boundary_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_reflected_domain_alternating_source_chain_sequence(
  seed: MocPhysicalPostShockFieldResult,
  initial_source_band: MocReflectedDomainAlternatingSourceResult,
  source_band_at: Callable[
    [
      MocPhysicalPostShockFieldResult,
      MocChainCell,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocReflectedDomainAlternatingSourceResult
    | MocChainTerminationDecision
    | None,
  ],
  *,
  start_x_m: float,
  end_x_m: float,
  compression_amplitude_rad: float,
  outer_source_index: int = 0,
  use_outer_seed_attachment: bool = False,
  use_trace_referenced_profile: bool = False,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  attachment_angle_half_width_rad: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  policy: MocChainContinuationPolicy | None = None,
  _field_observer: Callable[
    [MocPhysicalPostShockFieldContinuationSolve, MocChainCell],
    None,
  ] | None = None,
) -> MocChainPlannerResult:
  """Plan a sequence of fresh alternating-source physical shock cells.

  ``initial_source_band`` supplies the domain for the first continued cell.
  Every later ``source_band_at`` call must return a newly solved alternating
  source band whose ``incoming_handoff`` is exactly the centerline trace
  supplied by the preceding accepted physical field.  A source band is never
  reused, even when a caller attaches a different handoff to a copied result.

  This is the multi-cell counterpart to
  :func:`plan_reflected_domain_alternating_source_chain`.  It makes the
  continued-chain orchestration seam executable while preserving the current
  fidelity boundary: the local physical field uses the explicit research
  compression envelope, and the canonical reflected free-boundary,
  mixed-regime, refinement, and external-validation gates remain pending.

  ``use_outer_seed_attachment`` opts into attaching each generated shock at
  the retained outgoing reflection-interface seed from its fresh source
  patch.  The default keeps the existing first-outer-row attachment behavior
  for callers that are not yet using a reflected-interface continuation.

  ``use_trace_referenced_profile`` separately opts into the exact reflected
  trace turn law for each generated field.  It requires seed attachment and
  remains disabled by default so the automatic multi-cell reference does not
  silently change its continuation law.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(
    initial_source_band,
    MocReflectedDomainAlternatingSourceResult,
  ):
    raise TypeError(
      'initial_source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  if not callable(source_band_at):
    raise TypeError('source_band_at must be callable')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if not isfinite(float(compression_amplitude_rad)) or compression_amplitude_rad <= 0.0:
    raise ValueError('compression_amplitude_rad must be finite and positive')
  if not isinstance(use_outer_seed_attachment, bool):
    raise ValueError('use_outer_seed_attachment must be a bool')
  if not isinstance(use_trace_referenced_profile, bool):
    raise ValueError('use_trace_referenced_profile must be a bool')
  if use_trace_referenced_profile and not use_outer_seed_attachment:
    raise ValueError(
      'use_trace_referenced_profile requires use_outer_seed_attachment'
    )
  if _field_observer is not None and not callable(_field_observer):
    raise TypeError('_field_observer must be callable when supplied')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)

  active_field = seed
  initial_attempt = True
  used_source_ids: set[int] = set()
  used_source_fingerprints: set[str] = set()
  source_attempts: list[dict[str, Any]] = []
  physical_field_results: list[
    MocReflectedDomainAlternatingPhysicalFieldResult
  ] = []

  def provider_failure(
    next_cell_index: int,
    message: str,
    *,
    reason: MocChainTerminationReason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': 'alternating-source-chain-sequence',
      'next_cell_index': next_cell_index,
      'alternating_source_reuse_policy': (
        'fresh-alternating-source-band-and-exact-incoming-handoff-required-per-cell'
      ),
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  def source_provider(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocReflectedDomainAlternatingSourceResult | MocChainTerminationDecision:
    nonlocal active_field, initial_attempt
    if initial_attempt:
      candidate: (
        MocReflectedDomainAlternatingSourceResult
        | MocChainTerminationDecision
        | None
      ) = initial_source_band
      role = 'initial-alternating-source-band'
      initial_attempt = False
    else:
      try:
        candidate = source_band_at(
          active_field,
          current,
          next_cell_index,
          incoming_handoff,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        source_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'alternating-source-band-provider',
          'provider_error': type(error).__name__,
          'fresh_source_band': False,
          'incoming_handoff_verified': False,
        })
        return provider_failure(
          next_cell_index,
          f'alternating source-band provider failed: {error}',
          reason=MocChainTerminationReason.SOLVER_ERROR,
        )
      role = 'alternating-source-band-provider'

    if candidate is None:
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_result': None,
        'fresh_source_band': False,
        'incoming_handoff_verified': False,
      })
      return provider_failure(
        next_cell_index,
        'alternating source-band provider returned no bounded source field',
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
      )
    if isinstance(candidate, MocChainTerminationDecision):
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_decision': candidate.as_report(),
        'fresh_source_band': False,
        'incoming_handoff_verified': False,
      })
      if candidate.physical_termination:
        return provider_failure(
          next_cell_index,
          (
            'alternating source-band provider cannot declare physical '
            'termination before a downstream shock solve'
          ),
          reason=MocChainTerminationReason.INVALID_INPUT,
        )
      return candidate
    if not isinstance(
      candidate,
      MocReflectedDomainAlternatingSourceResult,
    ):
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_result_type': type(candidate).__name__,
        'fresh_source_band': False,
        'incoming_handoff_verified': False,
      })
      return provider_failure(
        next_cell_index,
        (
          'alternating source-band provider must return a '
          'MocReflectedDomainAlternatingSourceResult, '
          'MocChainTerminationDecision, or None'
        ),
        reason=MocChainTerminationReason.INVALID_INPUT,
      )

    incoming_handoff_verified = candidate.incoming_handoff == incoming_handoff
    fingerprint = _alternating_source_band_fingerprint(candidate)
    source_is_fresh = id(candidate) not in used_source_ids
    geometry_is_fresh = fingerprint not in used_source_fingerprints
    if not incoming_handoff_verified:
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'alternating-source-band-handoff-seam',
        'source_band': candidate.as_report(),
        'incoming_handoff_sample_count': len(incoming_handoff),
        'source_band_handoff_sample_count': len(candidate.incoming_handoff),
        'incoming_handoff_verified': False,
        'fresh_source_band': source_is_fresh,
        'fresh_source_geometry': geometry_is_fresh,
        'source_band_fingerprint': fingerprint,
      })
      return provider_failure(
        next_cell_index,
        (
          'alternating source-band provider did not record the exact incoming '
          'centerline handoff from the prior physical field'
        ),
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        diagnostics={
          'incoming_handoff_sample_count': len(incoming_handoff),
          'source_band_handoff_sample_count': len(candidate.incoming_handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(incoming_handoff),
          'source_band_handoff_fingerprint': _handoff_fingerprint(
            candidate.incoming_handoff
          ),
        },
      )
    if not source_is_fresh or not geometry_is_fresh:
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'alternating-source-band-freshness-gate',
        'source_band': candidate.as_report(),
        'incoming_handoff_verified': True,
        'fresh_source_band': source_is_fresh,
        'fresh_source_geometry': geometry_is_fresh,
        'source_band_fingerprint': fingerprint,
      })
      return provider_failure(
        next_cell_index,
        (
          'alternating source band or its state-bearing geometry was reused; '
          'every continued cell requires a fresh bounded source solve'
        ),
        diagnostics={
          'incoming_handoff_verified': True,
          'fresh_source_band': source_is_fresh,
          'fresh_source_geometry': geometry_is_fresh,
          'source_band_fingerprint': fingerprint,
        },
      )
    if not candidate.source_field_verified:
      source_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'source_band': candidate.as_report(),
        'incoming_handoff_verified': True,
        'fresh_source_band': True,
        'fresh_source_geometry': True,
      })
      reason = (
        MocChainTerminationReason.INVALID_INPUT
        if candidate.status is MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT
        else MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      )
      return provider_failure(
        next_cell_index,
        (
          'alternating source-band provider returned a field that did not '
          f'pass bounded-source gates: {candidate.message}'
        ),
        reason=reason,
        diagnostics={'source_band': candidate.as_report()},
      )

    used_source_ids.add(id(candidate))
    used_source_fingerprints.add(fingerprint)
    source_attempts.append({
      'current_cell_index': current.cell_index,
      'next_cell_index': next_cell_index,
      'role': role,
      'source_band': candidate.as_report(),
      'incoming_handoff_sample_count': len(incoming_handoff),
      'incoming_handoff_verified': True,
      'fresh_source_band': True,
      'fresh_source_geometry': True,
      'source_band_fingerprint': fingerprint,
    })
    return candidate

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal active_field
    source = source_provider(current, next_cell_index, incoming_handoff)
    if isinstance(source, MocChainTerminationDecision):
      return source
    try:
      solved = solve_reflected_domain_alternating_physical_field(
        source,
        compression_amplitude_rad,
        outer_source_index=outer_source_index,
        use_outer_seed_attachment=use_outer_seed_attachment,
        use_trace_referenced_profile=use_trace_referenced_profile,
        target_centerline_y_m=target_centerline_y_m,
        target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
        attachment_angle_half_width_rad=attachment_angle_half_width_rad,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        incoming_handoff=incoming_handoff,
      )
      physical_field_results.append(solved)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return provider_failure(
        next_cell_index,
        f'alternating source physical-field solve failed: {error}',
        reason=MocChainTerminationReason.SOLVER_ERROR,
        diagnostics={'source_band': source.as_report()},
      )
    if (
      solved.converged
      and solved.field is not None
      and solved.field.converged
      and solved.field.physical_closure_verified
      and solved.state_sampling_available
      and solved.upstream_coupling_verified
    ):
      active_field = solved.field
      if _field_observer is not None:
        _field_observer(
          MocPhysicalPostShockFieldContinuationSolve(
            field=solved.field,
            end_x_m=current.end_x_m + cell_axial_length_m,
          ),
          current,
        )
      return MocPhysicalPostShockFieldContinuationSolve(
        field=solved.field,
        end_x_m=current.end_x_m + cell_axial_length_m,
      )

    if solved.status is MocReflectedDomainAlternatingPhysicalFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif solved.status is MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return provider_failure(
      next_cell_index,
      (
        'alternating source physical-field solve did not produce a complete '
        f'chain cell: {solved.message}'
      ),
      reason=reason,
      diagnostics={
        'source_band': source.as_report(),
        'physical_field': solved.as_report(),
      },
    )

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'alternating-reflected-source fresh-band physical shock-chain sequence; '
      'bounded research continuation; canonical free-boundary validation and '
      'production promotion pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  if physical_field_results:
    from exhaust_plume.validation.moc_measurements import (
      measure_moc_reflected_domain_alternating_physical_field_chain,
    )

    physical_field_chain_audit = (
      measure_moc_reflected_domain_alternating_physical_field_chain(
        tuple(physical_field_results),
      )
    )
    diagnostics.update({
      'alternating_physical_field_chain_audit': (
        physical_field_chain_audit.as_report()
      ),
      'alternating_physical_field_chain_audit_accepted': (
        physical_field_chain_audit.converged
      ),
    })
  else:
    diagnostics.update({
      'alternating_physical_field_chain_audit': None,
      'alternating_physical_field_chain_audit_accepted': False,
    })
  diagnostics.update({
    'alternating_source_chain_model': (
      'bounded-alternating-source-fresh-band-physical-field-sequence'
    ),
    'alternating_source_initial_band': initial_source_band.as_report(),
    'alternating_source_attempt_count': len(source_attempts),
    'alternating_source_attempts': source_attempts,
    'alternating_source_reuse_policy': (
      'fresh-alternating-source-band-and-exact-incoming-handoff-required-per-cell'
    ),
    'use_outer_seed_attachment': use_outer_seed_attachment,
    'use_trace_referenced_profile': use_trace_referenced_profile,
    'canonical_reflected_domain_closed': False,
    'physical_closure_pending': True,
    'canonical_free_boundary_pending': True,
    'external_validation_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_reflected_domain_alternating_source_chain_from_physical_field(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  compression_amplitude_rad: float,
  source_sample_count: int = 6,
  outer_source_index: int = 0,
  use_trace_referenced_profile: bool = False,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  attachment_angle_half_width_rad: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 3.0e-3,
  trace_forward_tolerance_m: float = 1.0e-4,
  trace_invariant_tolerance: float = 1.0e-10,
  source_position_tolerance_m: float = 3.0e-3,
  source_invariant_tolerance: float = 1.0e-10,
  source_pressure_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  total_cell_count: int | None = None,
  policy: MocChainContinuationPolicy | None = None,
  _field_observer: Callable[
    [MocPhysicalPostShockFieldContinuationSolve, MocChainCell],
    None,
  ] | None = None,
) -> MocChainPlannerResult:
  """Plan a fresh-band alternating chain from accepted physical fields.

  The first source band is projected from ``seed`` and each later band is
  projected from the field accepted for the preceding chain cell.  The
  projection preserves the exact centerline handoff, extracts the finite
  shock/ambient strip, reflects its terminal ``C+`` trace, and then solves a
  new alternating ``C-``/``C+`` source band.  A projection failure is kept as
  a typed non-physical chain stop; no stale source band or extrapolated state
  is substituted.

  When supplied, ``total_cell_count`` bounds a research prefix.  The final
  attempt is reported as a typed ``SOLVER_RETURNED_NO_NEXT_CELL`` decision,
  rather than being conflated with the policy's safety cell limit.

  ``use_trace_referenced_profile`` is an explicit research option passed to
  each physical-field continuation.  It requires the retained outer-seed
  attachment mode and remains disabled by default because a profile can close
  one sampled field without producing a usable terminal trace at the next
  remesh resolution.

  This wrapper makes the solver-owned continuation path usable without a
  caller fabricating a fresh source callback.  It remains a research
  reference: the local compression envelope, canonical reflected
  free-boundary/mixed-regime closure, refinement, and external validation are
  still separate gates, and no product provider consumes the result.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(use_trace_referenced_profile, bool):
    raise ValueError('use_trace_referenced_profile must be a bool')
  if total_cell_count is not None and (
    isinstance(total_cell_count, bool)
    or not isinstance(total_cell_count, int)
    or total_cell_count < 1
  ):
    raise ValueError('total_cell_count must be a positive integer when supplied')

  def field_handoff(
    field: MocPhysicalPostShockFieldResult,
  ) -> tuple[MocChainBoundarySample, ...]:
    try:
      states = tuple(field.centerline_boundary_states)
      pressures = tuple(field.centerline_boundary_total_pressure_Pa)
      if len(states) != len(pressures):
        return ()
      return tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(states, pressures, strict=True)
      )
    except (TypeError, ValueError):
      return ()

  def decision(
    reason: MocChainTerminationReason,
    message: str,
    *,
    next_cell_index: int,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': (
        'solver-generated-alternating-source-from-accepted-physical-field'
      ),
      'next_cell_index': next_cell_index,
      'source_derivation_model': (
        'accepted-field -> open-shock-ambient-strip -> '
        'centerline-reflection-patch -> alternating-source-band'
      ),
      'configured_total_cell_count': total_cell_count,
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  if total_cell_count == 1:
    def configured_prefix_stop(
      _current: MocChainCell,
      next_cell_index: int,
      _incoming_handoff: tuple[MocChainBoundarySample, ...],
    ) -> MocChainTerminationDecision:
      return decision(
        MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        (
          'alternating source chain reached its configured one-cell research '
          'prefix before deriving a downstream source band'
        ),
        next_cell_index=next_cell_index,
        diagnostics={'termination_model': 'configured-cell-count'},
      )

    prefix_policy = policy
    if (
      isinstance(prefix_policy, MocChainContinuationPolicy)
      and prefix_policy.max_cells < 2
    ):
      prefix_policy = replace(prefix_policy, max_cells=2)
    planner = plan_ambient_closed_post_shock_chain(
      seed,
      configured_prefix_stop,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      policy=prefix_policy,
      require_upstream_shock_coupling=True,
      claim_status=(
        'alternating-reflected-source fresh-band physical shock-chain sequence; '
        'bounded research continuation; canonical free-boundary validation and '
        'production promotion pending'
      ),
    )
    diagnostics = dict(planner.diagnostics)
    diagnostics.update({
      'source_derivation_model': (
        'accepted-field -> open-shock-ambient-strip -> '
        'centerline-reflection-patch -> alternating-source-band'
      ),
      'source_derivation_automatic': True,
      'source_sample_count': source_sample_count,
      'configured_total_cell_count': total_cell_count,
      'alternating_source_initial_band': None,
      'alternating_source_attempt_count': 0,
      'alternating_source_attempts': [],
      'alternating_source_reuse_policy': (
        'fresh-alternating-source-band-and-exact-incoming-handoff-required-per-cell'
      ),
      'source_projection_failure_policy': (
        'typed-open-physical-closure-or-upstream-field-stop; '
        'never-reuse-or-extrapolate-a-prior-source-band'
      ),
      'use_outer_seed_attachment': True,
      'use_trace_referenced_profile': use_trace_referenced_profile,
      'canonical_reflected_domain_closed': False,
      'canonical_free_boundary_pending': True,
      'external_validation_pending': True,
    })
    return replace(planner, diagnostics=diagnostics)

  def invalid_source(
    message: str,
    handoff: tuple[MocChainBoundarySample, ...],
    ambient_pressure: float | None = None,
  ) -> MocReflectedDomainAlternatingSourceResult:
    return MocReflectedDomainAlternatingSourceResult(
      status=MocReflectedDomainAlternatingSourceStatus.INVALID_INPUT,
      reflection_patch=None,
      centerline_source_states=(),
      outer_source_states=(),
      centerline_total_pressure_Pa=(),
      outer_total_pressure_Pa=(),
      outer_seed_state=None,
      outer_seed_total_pressure_Pa=None,
      ambient_pressure_Pa=ambient_pressure,
      incoming_trace_validation=None,
      incoming_trace_polarity=None,
      incoming_handoff=handoff,
      message=message,
    )

  def source_for_field(
    field: MocPhysicalPostShockFieldResult,
    handoff: tuple[MocChainBoundarySample, ...],
    *,
    next_cell_index: int,
    current_end_x_m: float,
  ) -> (
    MocReflectedDomainAlternatingSourceResult
    | MocChainTerminationDecision
  ):
    if not isinstance(field, MocPhysicalPostShockFieldResult):
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        'alternating source derivation received an invalid physical field',
        next_cell_index=next_cell_index,
      )
    expected_handoff = field_handoff(field)
    if handoff != expected_handoff:
      return decision(
        MocChainTerminationReason.STATE_NOT_CARRIED,
        'alternating source derivation did not receive the exact field centerline handoff',
        next_cell_index=next_cell_index,
        diagnostics={
          'incoming_handoff_sample_count': len(handoff),
          'expected_handoff_sample_count': len(expected_handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(handoff),
          'expected_handoff_fingerprint': _handoff_fingerprint(expected_handoff),
        },
      )
    if not field.converged or not field.physical_closure_verified:
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'alternating source derivation requires a converged ambient-closed physical field',
        next_cell_index=next_cell_index,
        diagnostics={'upstream_field_status': field.status.value},
      )
    if not field.state_sampling_available:
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        'alternating source derivation requires bounded field sampling',
        next_cell_index=next_cell_index,
        diagnostics={'upstream_field_status': field.status.value},
      )
    if not field.upstream_shock_coupling_verified:
      return decision(
        MocChainTerminationReason.STATE_NOT_CARRIED,
        'alternating source derivation requires retained upstream shock coupling',
        next_cell_index=next_cell_index,
        diagnostics={'upstream_field_status': field.status.value},
      )
    ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
    if ambient_pressure is None:
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'accepted physical field did not retain an ambient pressure for source derivation',
        next_cell_index=next_cell_index,
      )
    try:
      strip = field.as_open_shock_ambient_strip(
        trace_position_tolerance_m=trace_position_tolerance_m,
        trace_forward_tolerance_m=trace_forward_tolerance_m,
        trace_invariant_tolerance=trace_invariant_tolerance,
      )
      patch = assemble_terminal_trace_centerline_patch(
        strip,
        trace_position_tolerance_m=trace_position_tolerance_m,
        trace_forward_tolerance_m=trace_forward_tolerance_m,
        invariant_tolerance=trace_invariant_tolerance,
      )
      source = solve_reflected_domain_alternating_source(
        patch,
        ambient_pressure,
        source_sample_count=source_sample_count,
        position_tolerance_m=source_position_tolerance_m,
        trace_forward_tolerance_m=trace_forward_tolerance_m,
        invariant_tolerance=source_invariant_tolerance,
        pressure_tolerance=source_pressure_tolerance,
        incoming_handoff=handoff,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'accepted physical field could not produce a fresh alternating source band',
        next_cell_index=next_cell_index,
        diagnostics={
          'source_projection_error': str(error),
          'source_projection_error_type': type(error).__name__,
          'upstream_field_status': field.status.value,
        },
      )
    if source.converged:
      if (
        not isinstance(outer_source_index, int)
        or isinstance(outer_source_index, bool)
        or outer_source_index < 0
        or outer_source_index >= len(source.outer_source_states)
      ):
        return decision(
          MocChainTerminationReason.INVALID_INPUT,
          'outer_source_index did not select a generated alternating source point',
          next_cell_index=next_cell_index,
          diagnostics={'source_band': source.as_report()},
        )
      source_start = source.outer_source_states[outer_source_index]
      if source_start.x_m <= float(current_end_x_m) + float(position_tolerance_m):
        return decision(
          MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
          (
            'fresh alternating source band begins at or upstream of the '
            'current chain interface; no backtracking or source extrapolation '
            'was used'
          ),
          next_cell_index=next_cell_index,
          diagnostics={
            'source_start_point_m': (source_start.x_m, source_start.y_m),
            'current_end_x_m': float(current_end_x_m),
            'source_band': source.as_report(),
          },
        )
    return source

  initial_handoff = field_handoff(seed)
  initial_source_or_decision = source_for_field(
    seed,
    initial_handoff,
    next_cell_index=2,
    current_end_x_m=end_x_m,
  )
  if isinstance(initial_source_or_decision, MocChainTerminationDecision):
    initial_source = invalid_source(
      initial_source_or_decision.message,
      initial_handoff,
      seed.ambient_boundary.ambient_pressure_Pa,
    )
  else:
    initial_source = initial_source_or_decision

  def source_band_at(
    field: MocPhysicalPostShockFieldResult,
    _current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> (
    MocReflectedDomainAlternatingSourceResult
    | MocChainTerminationDecision
  ):
    if total_cell_count is not None and next_cell_index > total_cell_count:
      return decision(
        MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        (
          'alternating source chain reached its configured '
          f'{total_cell_count}-cell research prefix'
        ),
        next_cell_index=next_cell_index,
        diagnostics={'termination_model': 'configured-cell-count'},
      )
    return source_for_field(
      field,
      incoming_handoff,
      next_cell_index=next_cell_index,
      current_end_x_m=_current.end_x_m,
    )

  planner = plan_reflected_domain_alternating_source_chain_sequence(
    seed,
    initial_source,
    source_band_at,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    compression_amplitude_rad=compression_amplitude_rad,
    outer_source_index=outer_source_index,
    use_outer_seed_attachment=True,
    use_trace_referenced_profile=use_trace_referenced_profile,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    attachment_angle_half_width_rad=attachment_angle_half_width_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    attachment_pressure_tolerance=attachment_pressure_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_boundary_iterations=maximum_boundary_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    policy=policy,
    _field_observer=_field_observer,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'source_derivation_model': (
      'accepted-field -> open-shock-ambient-strip -> '
      'centerline-reflection-patch -> alternating-source-band'
    ),
    'source_derivation_automatic': True,
    'source_sample_count': source_sample_count,
    'trace_position_tolerance_m': float(trace_position_tolerance_m),
    'trace_forward_tolerance_m': float(trace_forward_tolerance_m),
    'trace_invariant_tolerance': float(trace_invariant_tolerance),
    'source_position_tolerance_m': float(source_position_tolerance_m),
    'source_invariant_tolerance': float(source_invariant_tolerance),
    'source_pressure_tolerance': float(source_pressure_tolerance),
    'configured_total_cell_count': total_cell_count,
    'source_projection_failure_policy': (
      'typed-open-physical-closure-or-upstream-field-stop; '
      'never-reuse-or-extrapolate-a-prior-source-band'
    ),
    'use_outer_seed_attachment': True,
    'use_trace_referenced_profile': use_trace_referenced_profile,
    'canonical_reflected_domain_closed': False,
    'canonical_free_boundary_pending': True,
    'external_validation_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_reflected_domain_solver_owned_first_cell_chain(
  seed: MocPhysicalPostShockFieldResult,
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  start_x_m: float,
  end_x_m: float,
  outer_source_index: int = 0,
  target_centerline_index: int | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  closure_tolerance_m: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  total_cell_count: int | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the source-owned first-cell shoot through the chain planner.

  ``source_band`` is the explicit Cauchy-data handoff for the first continued
  cell.  The planner checks that its incoming handoff is exactly the seed
  field's centerline trace, invokes the bounded endpoint solver once, and
  preserves that solver's typed decision.  A locally complete endpoint root
  still returns ``FIDELITY_NOT_ALLOWED`` because the source-owned solver has
  not closed the canonical reflected free-boundary/Euler problem.  A missing
  endpoint bracket remains an ``OPEN_PHYSICAL_CLOSURE`` stop.

  This adapter is intentionally a planner/mock seam: it does not convert a
  research trial into a chain cell, reuse a source band after a stop, or
  mutate any fast/reduced-order provider.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(
    source_band,
    MocReflectedDomainAlternatingSourceResult,
  ):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if total_cell_count is not None and (
    isinstance(total_cell_count, bool)
    or not isinstance(total_cell_count, int)
    or total_cell_count < 1
  ):
    raise ValueError('total_cell_count must be a positive integer when supplied')
  if policy is not None and not isinstance(policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')

  def field_handoff(
    field: MocPhysicalPostShockFieldResult,
  ) -> tuple[MocChainBoundarySample, ...]:
    states = tuple(field.centerline_boundary_states)
    pressures = tuple(field.centerline_boundary_total_pressure_Pa)
    if len(states) != len(pressures):
      return ()
    try:
      return tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(states, pressures, strict=True)
      )
    except (TypeError, ValueError):
      return ()

  seed_handoff = field_handoff(seed)
  source_handoff = tuple(source_band.incoming_handoff)
  solver_result: MocReflectedDomainSolverOwnedFirstCellResult | None = None
  solver_measurement: Any | None = None
  solver_error: str | None = None

  def stop(
    reason: MocChainTerminationReason,
    message: str,
    *,
    next_cell_index: int,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': 'solver-owned-first-cell-planner-adapter',
      'next_cell_index': next_cell_index,
      'canonical_reflected_domain_closed': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocChainTerminationDecision:
    nonlocal solver_error, solver_measurement, solver_result
    if total_cell_count is not None and next_cell_index > total_cell_count:
      return stop(
        MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        (
          'solver-owned first-cell planner reached its configured '
          f'{total_cell_count}-cell research prefix'
        ),
        next_cell_index=next_cell_index,
        diagnostics={'termination_model': 'configured-cell-count'},
      )
    if incoming_handoff != source_handoff or source_handoff != seed_handoff:
      return stop(
        MocChainTerminationReason.STATE_NOT_CARRIED,
        (
          'solver-owned first-cell planner requires the source band to carry '
          'the exact seed centerline handoff'
        ),
        next_cell_index=next_cell_index,
        diagnostics={
          'seed_handoff_sample_count': len(seed_handoff),
          'source_band_handoff_sample_count': len(source_handoff),
          'incoming_handoff_sample_count': len(incoming_handoff),
          'seed_handoff_fingerprint': _handoff_fingerprint(seed_handoff),
          'source_band_handoff_fingerprint': _handoff_fingerprint(source_handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(incoming_handoff),
        },
      )
    try:
      solver_result = solve_reflected_domain_solver_owned_first_cell(
        source_band,
        outer_source_index=outer_source_index,
        target_centerline_index=target_centerline_index,
        compression_amplitude_lower_rad=compression_amplitude_lower_rad,
        compression_amplitude_upper_rad=compression_amplitude_upper_rad,
        closure_tolerance_m=closure_tolerance_m,
        incoming_handoff=incoming_handoff,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        maximum_bracket_scan_samples=maximum_bracket_scan_samples,
      )
      from exhaust_plume.validation.moc_measurements import (
        measure_moc_reflected_domain_solver_owned_first_cell,
      )

      solver_measurement = measure_moc_reflected_domain_solver_owned_first_cell(
        solver_result,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      solver_error = f'{type(error).__name__}: {error}'
      return stop(
        MocChainTerminationReason.SOLVER_ERROR,
        f'solver-owned first-cell planner adapter failed: {error}',
        next_cell_index=next_cell_index,
      )
    return solver_result.as_chain_termination_decision()

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'solver-owned-first-cell-endpoint-planner-research-seam; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'solver_owned_first_cell_planner_model': (
      'seed-physical-field -> exact-centerline-handoff -> '
      'bounded-source-owned-first-cell-endpoint-shoot'
    ),
    'solver_owned_first_cell_source_band': source_band.as_report(),
    'solver_owned_first_cell_seed_handoff_verified': (
      source_handoff == seed_handoff
    ),
    'solver_owned_first_cell_seed_handoff_fingerprint': (
      _handoff_fingerprint(seed_handoff)
    ),
    'solver_owned_first_cell_source_handoff_fingerprint': (
      _handoff_fingerprint(source_handoff)
    ),
    'solver_owned_first_cell': (
      None if solver_result is None else solver_result.as_report()
    ),
    'solver_owned_first_cell_independent_measurement': (
      None
      if solver_measurement is None
      else solver_measurement.as_report()
    ),
    'solver_owned_first_cell_audit_accepted': bool(
      solver_measurement is not None
      and solver_measurement.converged
      and solver_measurement.fidelity_isolation_verified
      and solver_measurement.chain_promotion_blocked
      and not solver_measurement.production_claim_allowed
    ),
    'solver_owned_first_cell_error': solver_error,
    'configured_total_cell_count': total_cell_count,
    'canonical_reflected_domain_closed': False,
    'canonical_free_boundary_pending': True,
    'canonical_euler_pending': True,
    'external_validation_pending': True,
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_reflected_domain_global_shock_remesh_chain(
  seed: MocPhysicalPostShockFieldResult,
  source_band: MocReflectedDomainAlternatingSourceResult,
  *,
  start_x_m: float,
  end_x_m: float,
  outer_source_indices: Sequence[int] | None = None,
  target_centerline_indices: Sequence[int] | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  compression_envelope_skews: Sequence[float] = (-0.75, 0.0, 0.75),
  closure_tolerance_m: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  maximum_attempts: int = 64,
  total_cell_count: int | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run a bounded global reflected-shock remesh through the chain planner.

  The planner validates the exact seed centerline handoff, executes the
  independent global source-pair/profile sweep once, and preserves its typed
  endpoint decision.  A no-root sweep is an auditable research stop; a local
  root is still ``FIDELITY_NOT_ALLOWED`` until the canonical reflected
  free-boundary/Euler and external-validation gates are implemented.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(
    source_band,
    MocReflectedDomainAlternatingSourceResult,
  ):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  if total_cell_count is not None and (
    isinstance(total_cell_count, bool)
    or not isinstance(total_cell_count, int)
    or total_cell_count < 1
  ):
    raise ValueError('total_cell_count must be a positive integer when supplied')
  if policy is not None and not isinstance(policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')

  def field_handoff(
    field: MocPhysicalPostShockFieldResult,
  ) -> tuple[MocChainBoundarySample, ...]:
    states = tuple(field.centerline_boundary_states)
    pressures = tuple(field.centerline_boundary_total_pressure_Pa)
    if len(states) != len(pressures):
      return ()
    try:
      return tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(states, pressures, strict=True)
      )
    except (TypeError, ValueError):
      return ()

  seed_handoff = field_handoff(seed)
  source_handoff = tuple(source_band.incoming_handoff)
  solver_result: MocReflectedDomainGlobalShockRemeshResult | None = None
  solver_measurement: Any | None = None
  solver_euler_audits: tuple[dict[str, Any], ...] = ()
  solver_euler_boundary_curves: tuple[dict[str, Any], ...] = ()
  solver_error: str | None = None

  def stop(
    reason: MocChainTerminationReason,
    message: str,
    *,
    next_cell_index: int,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': 'global-reflected-shock-remesh-planner-adapter',
      'next_cell_index': next_cell_index,
      'canonical_reflected_domain_closed': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  def solve_next(
    _current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocChainTerminationDecision:
    nonlocal solver_error, solver_measurement, solver_result
    nonlocal solver_euler_audits, solver_euler_boundary_curves
    if total_cell_count is not None and next_cell_index > total_cell_count:
      return stop(
        MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        (
          'global reflected-shock remesh planner reached its configured '
          f'{total_cell_count}-cell research prefix'
        ),
        next_cell_index=next_cell_index,
        diagnostics={'termination_model': 'configured-cell-count'},
      )
    if incoming_handoff != source_handoff or source_handoff != seed_handoff:
      return stop(
        MocChainTerminationReason.STATE_NOT_CARRIED,
        (
          'global reflected-shock remesh planner requires the source band to '
          'carry the exact seed centerline handoff'
        ),
        next_cell_index=next_cell_index,
        diagnostics={
          'seed_handoff_sample_count': len(seed_handoff),
          'source_band_handoff_sample_count': len(source_handoff),
          'incoming_handoff_sample_count': len(incoming_handoff),
          'seed_handoff_fingerprint': _handoff_fingerprint(seed_handoff),
          'source_band_handoff_fingerprint': _handoff_fingerprint(source_handoff),
          'incoming_handoff_fingerprint': _handoff_fingerprint(incoming_handoff),
        },
      )
    try:
      solver_result = solve_reflected_domain_global_shock_remesh(
        source_band,
        outer_source_indices=outer_source_indices,
        target_centerline_indices=target_centerline_indices,
        compression_amplitude_lower_rad=compression_amplitude_lower_rad,
        compression_amplitude_upper_rad=compression_amplitude_upper_rad,
        compression_envelope_skews=compression_envelope_skews,
        closure_tolerance_m=closure_tolerance_m,
        incoming_handoff=incoming_handoff,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        maximum_bracket_scan_samples=maximum_bracket_scan_samples,
        maximum_attempts=maximum_attempts,
      )
      from exhaust_plume.validation.moc_measurements import (
        measure_moc_reflected_domain_global_shock_remesh,
      )

      solver_measurement = measure_moc_reflected_domain_global_shock_remesh(
        solver_result,
      )
      from exhaust_plume.validation import (
        measure_moc_physical_field_euler_audit,
      )

      audit_rows: list[dict[str, Any]] = []
      boundary_curve_rows: list[dict[str, Any]] = []
      for attempt_index, attempt in enumerate(solver_result.attempts):
        selected_field = attempt.first_cell_result.selected_physical_field
        field = None if selected_field is None else selected_field.field
        if field is None:
          audit_rows.append({
            'attempt_index': attempt_index,
            'outer_source_index': attempt.outer_source_index,
            'target_centerline_index': attempt.target_centerline_index,
            'compression_envelope_skew': attempt.compression_envelope_skew,
            'field_available': False,
            'audit': None,
          })
          boundary_curve_rows.append({
            'attempt_index': attempt_index,
            'outer_source_index': attempt.outer_source_index,
            'target_centerline_index': attempt.target_centerline_index,
            'compression_envelope_skew': attempt.compression_envelope_skew,
            'field_available': False,
            'curve': None,
            'message': 'selected physical field unavailable',
          })
          continue
        audit = measure_moc_physical_field_euler_audit(field)
        audit_rows.append({
          'attempt_index': attempt_index,
          'outer_source_index': attempt.outer_source_index,
          'target_centerline_index': attempt.target_centerline_index,
          'compression_envelope_skew': attempt.compression_envelope_skew,
          'field_available': True,
          'audit': audit.as_report(),
        })
        upstream_states = tuple(field.upstream_shock_boundary_states)
        upstream_total_pressures = tuple(
          field.upstream_shock_boundary_total_pressure_Pa
        )
        downstream_states = tuple(field.post_shock_boundary_states)
        points = tuple(field.shock_boundary_points_m)
        if not (
          len(upstream_states)
          == len(upstream_total_pressures)
          == len(downstream_states)
          == len(points)
          and len(points) >= 2
        ):
          boundary_curve_rows.append({
            'attempt_index': attempt_index,
            'outer_source_index': attempt.outer_source_index,
            'target_centerline_index': attempt.target_centerline_index,
            'compression_envelope_skew': attempt.compression_envelope_skew,
            'field_available': True,
            'curve': None,
            'message': (
              'selected physical field does not carry equal upstream, '
              'downstream, pressure, and shock-point samples'
            ),
          })
          continue
        upstream_static_pressures = tuple(
          pressure / (
            1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
          ) ** (state.gamma / (state.gamma - 1.0))
          for state, pressure in zip(
            upstream_states,
            upstream_total_pressures,
            strict=True,
          )
        )
        try:
          boundary_curve = fit_euler_consistent_shock_boundary(
            upstream_states,
            upstream_static_pressures,
            points,
            tuple(state.theta_rad for state in downstream_states),
            shock_angle_tolerance_rad=shock_angle_tolerance_rad,
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
          boundary_curve_rows.append({
            'attempt_index': attempt_index,
            'outer_source_index': attempt.outer_source_index,
            'target_centerline_index': attempt.target_centerline_index,
            'compression_envelope_skew': attempt.compression_envelope_skew,
            'field_available': True,
            'curve': None,
            'message': f'Euler-consistent shock boundary fit failed: {error}',
          })
          continue
        boundary_curve_rows.append({
          'attempt_index': attempt_index,
          'outer_source_index': attempt.outer_source_index,
          'target_centerline_index': attempt.target_centerline_index,
          'compression_envelope_skew': attempt.compression_envelope_skew,
          'field_available': True,
          'curve': boundary_curve.as_report(),
        })
      solver_euler_audits = tuple(audit_rows)
      solver_euler_boundary_curves = tuple(boundary_curve_rows)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      solver_error = f'{type(error).__name__}: {error}'
      return stop(
        MocChainTerminationReason.SOLVER_ERROR,
        f'global reflected-shock remesh planner adapter failed: {error}',
        next_cell_index=next_cell_index,
      )
    return solver_result.as_chain_termination_decision()

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'global-reflected-shock-remesh-planner-research-seam; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'global_reflected_shock_remesh_planner_model': (
      'seed-physical-field -> exact-centerline-handoff -> '
      'bounded-global-source-pair-and-profile-sweep'
    ),
    'global_reflected_shock_remesh_source_band': source_band.as_report(),
    'global_reflected_shock_remesh_seed_handoff_verified': (
      source_handoff == seed_handoff
    ),
    'global_reflected_shock_remesh_seed_handoff_fingerprint': (
      _handoff_fingerprint(seed_handoff)
    ),
    'global_reflected_shock_remesh_source_handoff_fingerprint': (
      _handoff_fingerprint(source_handoff)
    ),
    'global_reflected_shock_remesh': (
      None if solver_result is None else solver_result.as_report()
    ),
    'global_reflected_shock_remesh_independent_measurement': (
      None
      if solver_measurement is None
      else solver_measurement.as_report()
    ),
    'global_reflected_shock_remesh_euler_audits': solver_euler_audits,
    'global_reflected_shock_remesh_euler_audit_accepted': bool(
      solver_euler_audits
      and all(
        row['field_available']
        and row['audit'] is not None
        and row['audit']['checks']['local_euler_consistency_verified']
        for row in solver_euler_audits
      )
    ),
    'global_reflected_shock_remesh_euler_audit_required_for_promotion': True,
    'global_reflected_shock_remesh_euler_boundary_curves': (
      solver_euler_boundary_curves
    ),
    'global_reflected_shock_remesh_euler_boundary_accepted': bool(
      solver_euler_boundary_curves
      and all(
        row['field_available']
        and row['curve'] is not None
        and row['curve']['local_euler_verified']
        and row['curve']['orientation'] == 'mixed-characteristic-boundary'
        and row['curve']['companion_boundary_required']
        and row['curve']['chain_promotion_blocked']
        for row in solver_euler_boundary_curves
      )
    ),
    'global_reflected_shock_remesh_euler_boundary_required_for_promotion': True,
    'global_reflected_shock_remesh_audit_accepted': bool(
      solver_measurement is not None
      and solver_measurement.converged
      and solver_measurement.fidelity_isolation_verified
      and solver_measurement.chain_promotion_blocked
      and not solver_measurement.production_claim_allowed
    ),
    'global_reflected_shock_remesh_error': solver_error,
    'configured_total_cell_count': total_cell_count,
    'canonical_reflected_domain_closed': False,
    'canonical_free_boundary_pending': True,
    'canonical_euler_pending': True,
    'external_validation_pending': True,
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_reflected_domain_remesh_shock_chain_sequence(
  seed: MocPostShockCharacteristicFieldResult,
  remesh: MocReflectedDomainRemeshResult,
  remesh_at: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocReflectedDomainRemeshResult | MocChainTerminationDecision | None,
  ],
  *,
  start_point_at: Callable[
    [MocChainCell, int, MocReflectedDomainRemeshResult],
    tuple[float, float],
  ],
  start_x_m: float,
  end_x_m: float,
  end_x_at: Callable[
    [MocChainCell, int, MocReflectedDomainRemeshResult],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan continued shocks with a fresh reflected remesh for each cell.

  The callback must return a new reflected-domain result whose request records
  the exact incoming handoff supplied by the prior chain cell.  The generic
  source-strip sequence then enforces distinct result/field identities.  The
  wrapper exists to expose the reflected-domain seam without allowing a
  single-characteristic front or a reused source field to masquerade as a
  continued physical chain.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not isinstance(remesh, MocReflectedDomainRemeshResult):
    raise TypeError('remesh must be a MocReflectedDomainRemeshResult')
  if not callable(remesh_at):
    raise TypeError('remesh_at must be callable')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')

  continuation_by_id: dict[int, MocReflectedDomainRemeshResult] = {}
  initial_continuation = _reflected_domain_source_continuation(remesh)
  continuation_by_id[id(initial_continuation)] = remesh
  remesh_attempts: list[dict[str, Any]] = [{
    'current_cell_index': 1,
    'next_cell_index': 2,
    'role': 'initial-reflected-domain-remesh',
    'remesh': remesh.as_report(),
    'fresh_remesh': True,
    'fresh_source_field': remesh.source_strip is not None,
  }]

  def provider_failure(
    next_cell_index: int,
    message: str,
    *,
    reason: MocChainTerminationReason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': 'reflected-domain-remesh-sequence',
      'next_cell_index': next_cell_index,
      'reflected_domain_reuse_policy': (
        'fresh-reflected-domain-remesh-required-per-cell'
      ),
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  def source_at(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocSourceStripContinuationResult | MocChainTerminationDecision | None:
    try:
      candidate = remesh_at(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-provider',
        'provider_error': type(error).__name__,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        f'reflected-domain remesh provider failed: {error}',
        reason=MocChainTerminationReason.SOLVER_ERROR,
      )
    if candidate is None:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-provider',
        'provider_result': None,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        'reflected-domain remesh provider returned no bounded source field',
      )
    if isinstance(candidate, MocChainTerminationDecision):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-provider',
        'provider_decision': candidate.as_report(),
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      if candidate.physical_termination:
        return provider_failure(
          next_cell_index,
          'reflected-domain provider cannot declare physical termination '
          'from an unresolved remesh boundary',
        )
      return candidate
    if not isinstance(candidate, MocReflectedDomainRemeshResult):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-provider',
        'provider_result_type': type(candidate).__name__,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        'reflected-domain remesh provider must return a '
        'MocReflectedDomainRemeshResult, MocChainTerminationDecision, or None',
        reason=MocChainTerminationReason.INVALID_INPUT,
      )
    request = candidate.request
    handoff_verified = bool(
      request is not None and request.incoming_handoff == incoming_handoff
    )
    if not handoff_verified:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-handoff-seam',
        'remesh': candidate.as_report(),
        'incoming_handoff_sample_count': len(incoming_handoff),
        'remesh_request_incoming_handoff_sample_count': (
          None if request is None else len(request.incoming_handoff)
        ),
        'incoming_handoff_verified': False,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        (
          'reflected-domain remesh provider did not record the exact prior '
          'chain handoff in its request'
        ),
        diagnostics={
          'incoming_handoff_sample_count': len(incoming_handoff),
          'remesh_request_incoming_handoff_sample_count': (
            None if request is None else len(request.incoming_handoff)
          ),
          'incoming_handoff_verified': False,
        },
      )
    continuation = _reflected_domain_source_continuation(candidate)
    continuation_by_id[id(continuation)] = candidate
    remesh_attempts.append({
      'current_cell_index': current.cell_index,
      'next_cell_index': next_cell_index,
      'role': 'reflected-domain-remesh-provider',
      'remesh': candidate.as_report(),
      'incoming_handoff_sample_count': len(incoming_handoff),
      'incoming_handoff_verified': True,
      'fresh_remesh': True,
      'fresh_source_field': candidate.source_strip is not None,
    })
    return continuation

  def source_start(
    current: MocChainCell,
    next_cell_index: int,
    continuation: MocSourceStripContinuationResult,
  ) -> tuple[float, float]:
    candidate = continuation_by_id.get(id(continuation))
    if candidate is None:
      raise ValueError(
        'reflected-domain planner lost the source-remesh provenance mapping'
      )
    return start_point_at(current, next_cell_index, candidate)

  def source_end(
    current: MocChainCell,
    next_cell_index: int,
    continuation: MocSourceStripContinuationResult,
  ) -> float:
    candidate = continuation_by_id.get(id(continuation))
    if candidate is None:
      raise ValueError(
        'reflected-domain planner lost the source-remesh provenance mapping'
      )
    assert end_x_at is not None
    return end_x_at(current, next_cell_index, candidate)

  planner = plan_source_strip_shock_chain_sequence(
    seed,
    initial_continuation,
    source_at,
    start_point_at=source_start,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    end_x_at=(source_end if end_x_at is not None else None),
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'reflected_domain_chain_model': (
      'bounded-reflected-domain-remesh-fresh-domain-sequence'
    ),
    'reflected_domain_remesh': remesh.as_report(),
    'reflected_domain_remesh_attempt_count': len(remesh_attempts),
    'reflected_domain_remesh_attempts': remesh_attempts,
    'reflected_domain_reuse_policy': (
      'fresh-reflected-domain-remesh-required-per-cell'
    ),
    'canonical_reflected_domain_closed': False,
    'physical_closure_pending': True,
  })
  return replace(
    planner,
    claim_status=(
      'reflected-domain-remesh shock-chain sequence; fresh bounded source per '
      'cell; canonical free-boundary and physical closure pending'
    ),
    diagnostics=diagnostics,
  )
####


def plan_reflected_domain_remesh_ambient_closed_chain(
  seed: MocPhysicalPostShockFieldResult,
  initial_remesh: MocReflectedDomainRemeshResult,
  remesh_at: Callable[
    [
      MocPhysicalPostShockFieldResult,
      MocChainCell,
      int,
      tuple[MocChainBoundarySample, ...],
    ],
    MocReflectedDomainRemeshResult | MocChainTerminationDecision | None,
  ],
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocSolverGeneratedAmbientClosedPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan physical shock cells from fresh reflected-domain remeshes.

  ``initial_remesh`` supplies the bounded Cauchy domain for cell two.  Every
  later call to ``remesh_at`` must return a new remesh whose request records the
  exact centerline handoff from the currently accepted cell.  Each accepted
  remesh is adapted to the real ambient-pressure/centerline-reflection field
  solver; it is never passed to the source-strip-only shock adapter.

  This is the first planner seam that joins the reflected-domain remesher to a
  physical ambient-closed field solve.  It remains research-only: the outer
  source curve is explicit caller-owned Cauchy data, entropy is still the
  remesh's uniform-total-pressure model, and canonical free-boundary closure
  is not inferred from a successful cell prefix.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not isinstance(initial_remesh, MocReflectedDomainRemeshResult):
    raise TypeError(
      'initial_remesh must be a MocReflectedDomainRemeshResult'
    )
  if not callable(remesh_at):
    raise TypeError('remesh_at must be callable')
  fixture = (
    MocSolverGeneratedAmbientClosedPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(
    fixture,
    MocSolverGeneratedAmbientClosedPostShockChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocSolverGeneratedAmbientClosedPostShockChainReference'
    )
  if fixture.upstream_source_mode is not MocAmbientClosedChainSourceMode.PREVIOUS_FIELD:
    raise ValueError(
      'reflected-domain remesh continuation owns the upstream source; '
      'reference.upstream_source_mode must be PREVIOUS_FIELD'
    )

  used_remesh_ids: set[int] = set()
  used_strip_fingerprints: set[str] = set()
  remesh_attempts: list[dict[str, Any]] = []
  active_field = seed
  first_attempt = True

  def provider_failure(
    next_cell_index: int,
    message: str,
    *,
    reason: MocChainTerminationReason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    payload: dict[str, Any] = {
      'termination_model': 'reflected-domain-remesh-ambient-closed-chain',
      'next_cell_index': next_cell_index,
      'reflected_domain_reuse_policy': (
        'fresh-reflected-domain-remesh-and-source-strip-required-per-cell'
      ),
    }
    if diagnostics is not None:
      payload.update(diagnostics)
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics=payload,
    )

  def source_provider(
    current_field: MocPhysicalPostShockFieldResult,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocBoundedUpstreamFieldSource | MocChainTerminationDecision | None:
    nonlocal first_attempt
    if first_attempt:
      candidate: MocReflectedDomainRemeshResult | MocChainTerminationDecision | None = (
        initial_remesh
      )
      role = 'initial-reflected-domain-remesh'
      first_attempt = False
    else:
      try:
        candidate = remesh_at(
          current_field,
          current,
          next_cell_index,
          incoming_handoff,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        remesh_attempts.append({
          'current_cell_index': current.cell_index,
          'next_cell_index': next_cell_index,
          'role': 'reflected-domain-remesh-provider',
          'provider_error': type(error).__name__,
          'fresh_remesh': False,
          'fresh_source_field': False,
        })
        return provider_failure(
          next_cell_index,
          f'reflected-domain remesh provider failed: {error}',
          reason=MocChainTerminationReason.SOLVER_ERROR,
        )
      role = 'reflected-domain-remesh-provider'

    if candidate is None:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_result': None,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        'reflected-domain remesh provider returned no bounded source field',
      )
    if isinstance(candidate, MocChainTerminationDecision):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_decision': candidate.as_report(),
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      if candidate.physical_termination:
        return provider_failure(
          next_cell_index,
          (
            'reflected-domain remesh provider cannot declare physical '
            'termination before a downstream shock solve'
          ),
          reason=MocChainTerminationReason.INVALID_INPUT,
        )
      return candidate
    if not isinstance(candidate, MocReflectedDomainRemeshResult):
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'provider_result_type': type(candidate).__name__,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        (
          'reflected-domain remesh provider must return a '
          'MocReflectedDomainRemeshResult, MocChainTerminationDecision, or None'
        ),
        reason=MocChainTerminationReason.INVALID_INPUT,
      )

    request = candidate.request
    incoming_handoff_verified = bool(
      request is not None and request.incoming_handoff == incoming_handoff
    )
    if not incoming_handoff_verified:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-handoff-seam',
        'remesh': candidate.as_report(),
        'incoming_handoff_sample_count': len(incoming_handoff),
        'remesh_request_incoming_handoff_sample_count': (
          None if request is None else len(request.incoming_handoff)
        ),
        'incoming_handoff_verified': False,
        'fresh_remesh': False,
        'fresh_source_field': False,
      })
      return provider_failure(
        next_cell_index,
        (
          'reflected-domain remesh provider did not record the exact incoming '
          'centerline handoff'
        ),
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        diagnostics={
          'incoming_handoff_sample_count': len(incoming_handoff),
          'remesh_request_incoming_handoff_sample_count': (
            None if request is None else len(request.incoming_handoff)
          ),
          'incoming_handoff_verified': False,
        },
      )

    strip_fingerprint = _characteristic_strip_fingerprint(candidate.source_strip)
    remesh_is_fresh = id(candidate) not in used_remesh_ids
    strip_is_fresh = (
      candidate.source_strip is not None
      and strip_fingerprint is not None
      and strip_fingerprint not in used_strip_fingerprints
    )
    if not remesh_is_fresh or not strip_is_fresh:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': 'reflected-domain-remesh-freshness-gate',
        'remesh': candidate.as_report(),
        'incoming_handoff_verified': True,
        'fresh_remesh': remesh_is_fresh,
        'fresh_source_field': strip_is_fresh,
        'source_strip_fingerprint': strip_fingerprint,
      })
      return provider_failure(
        next_cell_index,
        (
          'reflected-domain remesh or source strip was reused; every continued '
          'cell requires a fresh bounded upstream domain'
        ),
        diagnostics={
          'incoming_handoff_verified': True,
          'fresh_remesh': remesh_is_fresh,
          'fresh_source_field': strip_is_fresh,
          'source_strip_fingerprint': strip_fingerprint,
        },
      )

    if not candidate.state_sampling_available:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'remesh': candidate.as_report(),
        'incoming_handoff_verified': True,
        'fresh_remesh': True,
        'fresh_source_field': False,
      })
      decision = candidate.as_chain_termination_decision()
      return provider_failure(
        next_cell_index,
        decision.message,
        reason=decision.reason,
        diagnostics={
          'remesh': candidate.as_report(),
          'incoming_handoff_verified': True,
          'fresh_remesh': True,
          'fresh_source_field': False,
        },
      )

    used_remesh_ids.add(id(candidate))
    if strip_fingerprint is not None:
      used_strip_fingerprints.add(strip_fingerprint)
    try:
      source = MocBoundedUpstreamFieldSource.from_reflected_domain_remesh(
        candidate,
        sample_position_tolerance_m=fixture.source_sample_position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      remesh_attempts.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'role': role,
        'remesh': candidate.as_report(),
        'incoming_handoff_verified': True,
        'fresh_remesh': True,
        'fresh_source_field': False,
        'adapter_error': type(error).__name__,
      })
      return provider_failure(
        next_cell_index,
        f'reflected-domain remesh could not become a bounded source: {error}',
        reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      )
    remesh_attempts.append({
      'current_cell_index': current.cell_index,
      'next_cell_index': next_cell_index,
      'role': role,
      'remesh': candidate.as_report(),
      'incoming_handoff_sample_count': len(incoming_handoff),
      'incoming_handoff_verified': True,
      'fresh_remesh': True,
      'fresh_source_field': True,
      'source_strip_fingerprint': strip_fingerprint,
      'source': source.as_report(),
    })
    return source

  fixture = replace(fixture, upstream_source_provider=source_provider)

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal active_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      active_field,
    )
    if isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      active_field = solved.field
    return solved

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'reflected-domain-remesh to ambient-closed physical-field chain; '
      'explicit Cauchy outer source; canonical free-boundary and external '
      'validation pending'
    ),
  )
  diagnostics = dict(planner.diagnostics)
  diagnostics.update({
    'reflected_domain_ambient_closed_chain_model': (
      'solver-generated-reflected-domain-cauchy-remesh-plus-ambient-closed-'
      'physical-field-solve'
    ),
    'reference': fixture.as_report(),
    'initial_reflected_domain_remesh': initial_remesh.as_report(),
    'reflected_domain_remesh_attempt_count': len(remesh_attempts),
    'reflected_domain_remesh_attempts': remesh_attempts,
    'reflected_domain_reuse_policy': (
      'fresh-reflected-domain-remesh-and-source-strip-required-per-cell'
    ),
    'canonical_reflected_domain_closed': False,
    'free_boundary_verified': False,
    'physical_chain_promotion_allowed': False,
    'external_validation_pending': True,
  })
  return replace(planner, diagnostics=diagnostics)
####


def plan_post_shock_field_invariant_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[
    [MocPostShockCharacteristicFieldResult, int, tuple[float, float]],
    float,
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan field-coupled cells with an explicit downstream invariant law.

  The invariant callback receives the currently accepted bounded field, so a
  caller can derive a target from the local upstream state and pressure before
  the continuation solver inverts it through attached compression.  The
  planner replaces the upstream field only after a complete cell is returned;
  typed physical and numerical stops remain visible in the step audit.

  This is a research planner.  A selected invariant is an explicit downstream
  condition, not a canonical mixed-regime closure or a production shock
  placement model.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if not isinstance(downstream_invariant_family, CharacteristicFamily):
    raise TypeError(
      'downstream_invariant_family must be a CharacteristicFamily'
    )
  if not callable(downstream_invariant_at):
    raise TypeError('downstream_invariant_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_field_with_invariant_boundary_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      start_point_m=start_point,
      end_x_m=next_end_x,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_at=(
        lambda index, point: downstream_invariant_at(
          current_field,
          index,
          point,
        )
      ),
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-post-shock-field-invariant-coupled-planner; '
      'selected-invariant-and-external-validation-pending'
    ),
  )
####


def plan_ambient_pressure_field_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  closure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan repeated ambient-pressure-conditioned field re-solves.

  Each candidate next shock samples only the currently accepted post-shock
  field.  The field is replaced after, and only after, the ambient perimeter,
  shock fit, exact incoming handoff, and upstream coupling gates pass.  A
  bracket or bounded-domain failure becomes a typed planner stop; the planner
  remains a research lane and never changes the fast or reduced-order
  provider claims.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      lambda point: current_field.state_at(
        point,
        position_tolerance_m=position_tolerance_m,
      ),
      lambda point: current_field.static_pressure_at(
        point,
        position_tolerance_m=position_tolerance_m,
      ),
      start_point,
      next_end_x,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      closure_tolerance=closure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'ambient-pressure-field-coupled-planner; exact-handoff-and-'
      'external-validation-pending'
    ),
  )
####


def plan_ambient_closed_post_shock_chain(
  seed: MocPhysicalPostShockFieldResult,
  solve_next: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocPhysicalPostShockFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = True,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Audit continuation of solver-owned ambient-closed physical cells.

  This planner is the physical-field counterpart to the prescribed chain
  mock.  Every callback receives the prior closed cell's centerline trace and
  must return a newly assembled ambient-closed field that records the exact
  incoming handoff.  It remains a research planner until the canonical
  reflected upstream domain and independent validation gates pass.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if not callable(solve_next):
    raise TypeError('solve_next must be callable')
  steps: list[MocChainPlannerStep] = []

  def wrapped(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision | None:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError(
        'planner callback received a handoff different from the current physical cell'
      )
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      incoming_handoff,
      previous_result_handoff_fingerprint=(
        steps[-1].result_handoff_fingerprint if steps else None
      ),
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

  chain = continue_ambient_closed_post_shock_chain(
    seed,
    wrapped,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=require_upstream_shock_coupling,
  )
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    steps=tuple(steps),
    claim_status=(
      'ambient-closed-physical-field-chain; canonical-reflected-domain-and-'
      'external-validation-pending'
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_solver_generated_ambient_closed_post_shock_chain_reference(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocSolverGeneratedAmbientClosedPostShockChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the solver-generated ambient-closed research chain reference."""

  fixture = (
    MocSolverGeneratedAmbientClosedPostShockChainReference()
    if reference is None
    else reference
  )
  if not isinstance(
    fixture,
    MocSolverGeneratedAmbientClosedPostShockChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocSolverGeneratedAmbientClosedPostShockChainReference'
    )
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
    )
    if isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      current_field = solved.field
    return solved

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'solver-generated-ambient-closed-physical-field-chain-reference; '
      'reflected-upstream-remesher-and-external-validation-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'solver_generated_ambient_closed_chain_reference': fixture.as_report(),
      'upstream_field_replacement_policy': (
        'replace-only-after-complete-ambient-closed-physical-field-solve'
      ),
      'source_provider_policy': (
        'bounded-callback-source-or-previous-field; no extrapolation'
      ),
    },
  )
####


def plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocTerminalReflectionPatchAmbientClosureChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  _field_observer: Callable[
    [MocPhysicalPostShockFieldContinuationSolve, MocChainCell],
    None,
  ] | None = None,
) -> MocChainPlannerResult:
  """Plan a bounded continued chain from reflected terminal patches.

  Each accepted continuation replaces the active upstream field.  The
  configured cell count is a research stop, so a partial prefix plus a typed
  downstream closure/boundary decision is expected while the reflected
  free-boundary lane is still being developed.
  """

  fixture = (
    MocTerminalReflectionPatchAmbientClosureChainReference()
    if reference is None
    else reference
  )
  if not isinstance(
    fixture,
    MocTerminalReflectionPatchAmbientClosureChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocTerminalReflectionPatchAmbientClosureChainReference'
    )
  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if _field_observer is not None and not callable(_field_observer):
    raise TypeError('_field_observer must be callable when supplied')
  try:
    requested_end_x = float(end_x_m)
  except (TypeError, ValueError) as error:
    raise ValueError('end_x_m must be numeric') from error
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  if not seed.ambient_boundary_points_m:
    raise ValueError(
      'seed must retain a downstream ambient boundary endpoint for the '
      'shared first-cell interface'
    )
  seed_end_x = float(seed.ambient_boundary_points_m[-1][0])
  if not isfinite(seed_end_x) or seed_end_x <= float(start_x_m):
    raise ValueError(
      'seed ambient boundary endpoint must be finite and downstream of '
      'start_x_m'
    )
  if requested_end_x <= seed_end_x:
    raise ValueError(
      'end_x_m must be downstream of the seed ambient boundary endpoint'
    )
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      end_x_m=requested_end_x,
    )
    if isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      current_field = solved.field
      if _field_observer is not None:
        _field_observer(solved, current)
    return solved

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    # The seed's actual ambient endpoint is the shared interface.  The
    # caller's end_x_m is retained as the continuation solver's axial limit
    # and is passed through fixture.solve_next above.
    end_x_m=seed_end_x,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'solver-generated-terminal-reflection-patch-ambient-closure-chain; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
  )
  return replace(
    planner,
    diagnostics={
      'terminal_reflection_patch_ambient_closure_chain_reference': (
        fixture.as_report()
      ),
      'upstream_field_replacement_policy': (
        'replace-only-after-complete-ambient-closed-physical-field-solve'
      ),
      'endpoint_policy': (
        'use-next-field-ambient-boundary-endpoint; requested-end-x-is-an-'
        'axial-limit; no fabricated interface'
      ),
      'requested_end_x_m': requested_end_x,
      'seed_interface_end_x_m': seed_end_x,
      'fidelity_boundary': (
        'research-only-solver-owned-planar-MOC; no basic/reduced-provider-'
        'promotion'
      ),
    },
  )
####


def _capture_terminal_reflection_patch_prefix(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocTerminalReflectionPatchAmbientClosureChainReference,
  policy: MocChainContinuationPolicy | None,
) -> tuple[
  MocChainPlannerResult,
  MocPhysicalPostShockFieldResult | None,
  tuple[MocPhysicalPostShockFieldResult, ...],
  int | None,
  MocChainCell | None,
]:
  """Run one reflected prefix and retain its exact accepted field handoff."""

  requested_end_x = float(end_x_m)
  if not isfinite(requested_end_x):
    raise ValueError('end_x_m must be finite')
  if not seed.ambient_boundary_points_m:
    raise ValueError(
      'seed must retain a downstream ambient boundary endpoint for the '
      'shared first-cell interface'
    )
  seed_end_x = float(seed.ambient_boundary_points_m[-1][0])
  if not isfinite(seed_end_x) or seed_end_x <= float(start_x_m):
    raise ValueError(
      'seed ambient boundary endpoint must be finite and downstream of '
      'start_x_m'
    )
  if requested_end_x <= seed_end_x:
    raise ValueError(
      'end_x_m must be downstream of the seed ambient boundary endpoint'
    )

  captured_field: MocPhysicalPostShockFieldResult | None = None
  captured_fields: list[MocPhysicalPostShockFieldResult] = [seed]
  captured_cell_index: int | None = None

  def observe(
    solved: MocPhysicalPostShockFieldContinuationSolve,
    current: MocChainCell,
  ) -> None:
    nonlocal captured_cell_index, captured_field
    captured_field = solved.field
    captured_fields.append(solved.field)
    captured_cell_index = current.cell_index + 1

  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = reference.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      end_x_m=requested_end_x,
    )
    if isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      current_field = solved.field
      observe(solved, current)
    return solved

  prefix = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=seed_end_x,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'solver-generated-terminal-reflection-patch-ambient-closure-chain; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
  )
  prefix_cell = (
    prefix.chain.cells[-1]
    if prefix.chain.resolved and prefix.chain.cells
    else None
  )
  return (
    prefix,
    captured_field,
    tuple(captured_fields),
    captured_cell_index,
    prefix_cell,
  )


def plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_mixed_regime(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  reference: MocTerminalReflectionPatchAmbientClosureChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  terminal_policy: MocChainContinuationPolicy | None = None,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
  solve_field: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeFieldResult | None,
  ] | None = None,
  control_section: MocMixedRegimeControlSection | None = None,
  use_integrated_flux: bool = False,
  attach_mixed_regime_field: bool = False,
  free_boundary_refinement_sample_counts: Sequence[int] | None = None,
  mixed_regime_entropy_source_arc_length_m: Sequence[float] | None = None,
  mixed_regime_entropy_streamline_ids: Sequence[int] | None = None,
) -> MocAmbientClosedPostShockChainTerminalPlannerResult:
  """Continue reflected physical cells, then run one terminal handoff.

  The reflected-patch reference owns the accepted supersonic prefix.  Once a
  new physical field has actually been accepted into that prefix, this
  wrapper sends that final field through the one-step terminal-patch planner.
  The terminal planner may exercise the prescribed mixed-regime mock or the
  scalar free-boundary reference, but its result remains separate from the
  supersonic cells.  If the prefix stops before a new field is accepted, no
  terminal result is fabricated.

  This is a research orchestration helper.  It does not promote the chain or
  any mixed-regime field into the fast visualization or reduced-order
  providers, and the combined result always reports ``production_claim_allowed``
  as false.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  fixture = (
    MocTerminalReflectionPatchAmbientClosureChainReference()
    if reference is None
    else reference
  )
  if not isinstance(
    fixture,
    MocTerminalReflectionPatchAmbientClosureChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocTerminalReflectionPatchAmbientClosureChainReference'
    )
  if policy is not None and not isinstance(policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')
  if terminal_policy is not None and not isinstance(
    terminal_policy,
    MocChainContinuationPolicy,
  ):
    raise TypeError(
      'terminal_policy must be a MocChainContinuationPolicy or None'
    )
  if not isinstance(attach_mixed_regime_field, bool):
    raise TypeError('attach_mixed_regime_field must be a bool')
  if control_section is not None and not isinstance(
    control_section,
    MocMixedRegimeControlSection,
  ):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection or None'
    )
  if not isinstance(use_integrated_flux, bool):
    raise TypeError('use_integrated_flux must be a bool')
  if control_section is not None and solver is None:
    raise ValueError('control_section requires the solver-generated reference')
  if use_integrated_flux and control_section is None:
    raise ValueError('use_integrated_flux requires a control_section')
  if use_integrated_flux and solver is None:
    raise ValueError('use_integrated_flux requires the solver-generated reference')
  if control_section is not None and (mock is not None or solve_field is not None):
    raise ValueError('control_section is supported only by the solver-generated reference')
  if (
    mixed_regime_entropy_source_arc_length_m is None
  ) != (
    mixed_regime_entropy_streamline_ids is None
  ):
    raise ValueError(
      'mixed_regime_entropy_source_arc_length_m and '
      'mixed_regime_entropy_streamline_ids must be supplied together'
    )

  (
    prefix,
    captured_field,
    captured_fields,
    captured_cell_index,
    prefix_cell,
  ) = _capture_terminal_reflection_patch_prefix(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    reference=fixture,
    policy=policy,
  )
  terminal: MocPhysicalPostShockTerminalPatchPlannerResult | None = None
  diagnostics: dict[str, Any] = {
    'planner_model': (
      'ambient-closed-post-shock-chain-terminal-reflection-patch-'
      'mixed-regime'
    ),
    'prefix_cell_count': prefix.chain.cell_count,
    'prefix_field_count': len(captured_fields),
    'prefix_planner_kind': prefix.planner_kind.value,
    'prefix_planner_audit': None,
    'prefix_planner_audit_accepted': False,
    'prefix_physical_field_audit': None,
    'prefix_physical_field_audit_accepted': False,
    'terminal_attempted': False,
    'terminal_input_cell_index': (
      None if prefix_cell is None else prefix_cell.cell_index
    ),
    'terminal_input_cell_end_x_m': (
      None if prefix_cell is None else prefix_cell.end_x_m
    ),
    'terminal_end_x_m': float(terminal_end_x_m),
    'terminal_mixed_regime_field_attached': attach_mixed_regime_field,
    'fidelity_boundary': (
      'research-only continued supersonic prefix plus terminal mixed-regime '
      'handoff; no basic/reduced-provider promotion'
    ),
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
  }
  try:
    # Keep validation imports local: validation imports the model package while
    # this planner is imported during package startup.
    from exhaust_plume.validation.moc_measurements import (
      measure_moc_ambient_closed_physical_field_chain,
      measure_moc_chain_planner,
    )

    prefix_planner_measurement = measure_moc_chain_planner(prefix)
    prefix_physical_field_measurement = (
      measure_moc_ambient_closed_physical_field_chain(captured_fields)
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    diagnostics['prefix_audit_error'] = str(error)
  else:
    diagnostics['prefix_planner_audit'] = prefix_planner_measurement.as_report()
    diagnostics['prefix_planner_audit_accepted'] = bool(
      prefix_planner_measurement.converged
      and prefix_planner_measurement.termination_verified
      and prefix_planner_measurement.fidelity_isolation_verified
      and not prefix_planner_measurement.production_claim_allowed
    )
    diagnostics['prefix_physical_field_audit'] = (
      prefix_physical_field_measurement.as_report()
    )
    diagnostics['prefix_physical_field_audit_accepted'] = bool(
      prefix_physical_field_measurement.converged
      and prefix_physical_field_measurement.physical_closure_verified
      and prefix_physical_field_measurement.chain_promotion_blocked
      and not prefix_physical_field_measurement.production_claim_allowed
    )
  if (
    prefix_cell is None
    or captured_field is None
    or captured_cell_index != prefix_cell.cell_index
    or prefix.chain.cell_count < 2
    or prefix.chain.cells[-1].cell_index != prefix.chain.cell_count
  ):
    diagnostics['terminal_attempt_message'] = (
      'continued prefix did not accept a new physical field; terminal '
      'mixed-regime handoff was not attempted'
    )
    return MocAmbientClosedPostShockChainTerminalPlannerResult(
      chain_planner=prefix,
      terminal_planner=None,
      planner_kind=prefix.planner_kind,
      claim_status=(
        'continued-terminal-reflection-patch-chain; terminal-transition-not-'
        'reached; canonical-reflected-free-boundary-and-external-validation-'
        'pending'
      ),
      diagnostics=diagnostics,
    )

  effective_terminal_policy = terminal_policy
  if effective_terminal_policy is None:
    effective_terminal_policy = MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    )
  diagnostics['terminal_attempted'] = True
  terminal = plan_ambient_closed_post_shock_chain_terminal_patch_with_mixed_regime(
    captured_field,
    start_x_m=prefix_cell.start_x_m,
    end_x_m=prefix_cell.end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    downstream_flow_angle_rad=0.0,
    sample_count=fixture.sample_count,
    branch=fixture.branch,
    trace_position_tolerance_m=fixture.trace_position_tolerance_m,
    seam_position_tolerance_m=fixture.seam_position_tolerance_m,
    position_tolerance_m=fixture.position_tolerance_m,
    invariant_tolerance=fixture.invariant_tolerance,
    shock_angle_tolerance_rad=fixture.shock_angle_tolerance_rad,
    maximum_segment_iterations=fixture.maximum_segment_iterations,
    policy=effective_terminal_policy,
    mock=mock,
    solver=solver,
    solve_field=solve_field,
    control_section=control_section,
    use_integrated_flux=use_integrated_flux,
    attach_mixed_regime_field=attach_mixed_regime_field,
    free_boundary_refinement_sample_counts=(
      free_boundary_refinement_sample_counts
    ),
    mixed_regime_entropy_source_arc_length_m=(
      mixed_regime_entropy_source_arc_length_m
    ),
    mixed_regime_entropy_streamline_ids=mixed_regime_entropy_streamline_ids,
  )
  diagnostics.update({
    'terminal_planner_kind': terminal.planner_kind.value,
    'terminal_resolved': terminal.resolved,
    'terminal_physical_termination': terminal.physical_termination,
    'terminal_physical_closure_verified': terminal.physical_closure_verified,
    'terminal_mixed_regime_model_closure_verified': (
      terminal.mixed_regime_model_closure_verified
    ),
    'terminal_report': terminal.as_report(),
  })
  return MocAmbientClosedPostShockChainTerminalPlannerResult(
    chain_planner=prefix,
    terminal_planner=terminal,
    planner_kind=prefix.planner_kind,
    claim_status=(
      'continued-terminal-reflection-patch-chain-with-mixed-regime; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
  )
####


def plan_prescribed_ambient_closed_post_shock_chain_mock(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  mock: MocPrescribedAmbientClosedPostShockChainMock | None = None,
  policy: MocChainContinuationPolicy | None = None,
  _field_observer: Callable[
    [MocPhysicalPostShockFieldContinuationSolve, MocChainCell],
    None,
  ] | None = None,
) -> MocChainPlannerResult:
  """Run a prescribed multi-cell mock through the physical-field solver.

  The mock is intentionally only a source of explicit candidate boundaries.
  It never owns the upstream state model: after a candidate succeeds, the
  returned physical field becomes the source for the next candidate.  A
  failed or typed-stop candidate leaves that accepted field untouched and
  the chain retains only its valid prefix.
  """

  fixture = (
    MocPrescribedAmbientClosedPostShockChainMock()
    if mock is None else mock
  )
  if not isinstance(fixture, MocPrescribedAmbientClosedPostShockChainMock):
    raise TypeError(
      'mock must be a MocPrescribedAmbientClosedPostShockChainMock'
    )
  if _field_observer is not None and not callable(_field_observer):
    raise TypeError('_field_observer must be callable when supplied')
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
    nonlocal current_field
    solved = fixture.solve_next(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
    )
    if isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      current_field = solved.field
      if _field_observer is not None:
        _field_observer(solved, current)
    return solved

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    claim_status=(
      'prescribed-ambient-closed-physical-field-chain-mock; '
      'canonical-reflected-free-boundary-and-external-validation-pending'
    ),
  )
  return replace(
    planner,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
    diagnostics={
      'prescribed_ambient_closed_chain_mock': fixture.as_report(),
      'upstream_field_replacement_policy': (
        'replace-only-after-complete-ambient-closed-physical-field-solve'
      ),
      'candidate_failure_policy': (
        'retain-valid-prefix-and-preserve-typed-upstream-boundary-stop'
      ),
    },
  )
####


@dataclass(frozen=True, slots=True)
class MocFirstCellResearchChainPlannerResult:
  """Research-only handoff from a local first-cell candidate to a chain.

  The geometry-owned first-cell candidate is a locally closed physical field,
  but it is not the canonical reflected free-boundary solution.  This wrapper
  makes the deliberate research handoff explicit: the candidate field may be
  used to exercise a reflected-patch continuation or a prescribed-boundary
  planner mock, while the candidate's production and canonical promotion
  gates remain false.

  ``physical_fields`` retains the exact seed and every accepted continuation
  returned by the planner.  It is carried so an independent validation
  operator can remeasure the complete handoff instead of trusting planner
  flags or serialized cell metadata.
  """

  candidate: MocFirstCellCandidateResult
  chain_planner: MocChainPlannerResult | None
  termination: MocChainTerminationDecision
  planner_kind: MocChainPlannerKind
  claim_status: str
  physical_fields: tuple[MocPhysicalPostShockFieldResult, ...] = ()
  candidate_measurement: Any | None = None
  chain_planner_measurement: Any | None = None
  physical_field_chain_measurement: Any | None = None
  research_chain_measurement: Any | None = None
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.candidate, MocFirstCellCandidateResult):
      raise TypeError('candidate must be a MocFirstCellCandidateResult')
    if self.chain_planner is not None and not isinstance(
      self.chain_planner,
      MocChainPlannerResult,
    ):
      raise TypeError(
        'chain_planner must be a MocChainPlannerResult or None'
      )
    if not isinstance(self.termination, MocChainTerminationDecision):
      raise TypeError(
        'termination must be a MocChainTerminationDecision'
      )
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    if self.chain_planner is not None and (
      self.chain_planner.planner_kind is not self.planner_kind
    ):
      raise ValueError(
        'planner_kind must match the continued-chain planner kind'
      )
    fields = tuple(self.physical_fields)
    if any(
      not isinstance(field, MocPhysicalPostShockFieldResult)
      for field in fields
    ):
      raise TypeError(
        'physical_fields must contain MocPhysicalPostShockFieldResult values'
      )
    if fields and self.candidate.field is not fields[0]:
      raise ValueError(
        'physical_fields must retain the exact candidate field as its first '
        'entry'
      )
    object.__setattr__(self, 'physical_fields', fields)
    for name in (
      'candidate_measurement',
      'chain_planner_measurement',
      'physical_field_chain_measurement',
      'research_chain_measurement',
    ):
      value = getattr(self, name)
      if value is not None and not callable(getattr(value, 'as_report', None)):
        raise TypeError(f'{name} must expose an as_report method when supplied')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(
      self,
      'diagnostics',
      MappingProxyType(dict(self.diagnostics)),
    )
  ####

  @property
  def cell_count(self) -> int:
    """Return the accepted research prefix count, including the seed."""

    return (
      0
      if self.chain_planner is None
      else self.chain_planner.chain.cell_count
    )
  ####

  @property
  def continued_cell_count(self) -> int:
    """Return the number of accepted cells after the candidate seed."""

    return max(0, self.cell_count - 1)
  ####

  @property
  def resolved(self) -> bool:
    """Whether the research prefix contains an accepted continuation."""

    return bool(
      self.continued_cell_count > 0
      and self.chain_planner is not None
      and self.chain_planner.chain.resolved
    )
  ####

  @property
  def first_cell_handoff_verified(self) -> bool:
    """Whether the candidate field passed the independent first-cell audit."""

    return bool(
      self.candidate.field is not None
      and self.physical_fields
      and self.physical_fields[0] is self.candidate.field
      and self.candidate.local_physical_closure_verified
      and self.candidate_measurement is not None
      and getattr(self.candidate_measurement, 'converged', False)
    )
  ####

  @property
  def handoff_links_verified(self) -> bool | None:
    """Return the independent planner/field-chain handoff result."""

    planner_links = None
    if self.chain_planner_measurement is not None:
      planner_links = getattr(
        self.chain_planner_measurement,
        'handoff_links_verified',
        None,
      )
    field_links = None
    if self.physical_field_chain_measurement is not None:
      field_links = getattr(
        self.physical_field_chain_measurement,
        'handoff_links_verified',
        None,
      )
    if planner_links is False or field_links is False:
      return False
    if planner_links is True and field_links is True:
      return True
    if self.chain_planner is not None:
      return self.chain_planner.handoff_links_verified
    return None
  ####

  @property
  def continued_chain_audit_verified(self) -> bool:
    """Whether both independent continued-chain measurements passed."""

    return bool(
      self.chain_planner is not None
      and self.chain_planner_measurement is not None
      and getattr(self.chain_planner_measurement, 'converged', False)
      and self.physical_field_chain_measurement is not None
      and getattr(self.physical_field_chain_measurement, 'converged', False)
      and self.handoff_links_verified is True
    )
  ####

  @property
  def research_audit_accepted(self) -> bool:
    """Whether the candidate-to-chain research evidence passed its audits."""

    return bool(
      self.resolved
      and self.first_cell_handoff_verified
      and self.continued_chain_audit_verified
      and self.research_chain_measurement is not None
      and getattr(self.research_chain_measurement, 'converged', False)
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Expose local physical closure without changing the fidelity ceiling."""

    return bool(
      self.physical_field_chain_measurement is not None
      and getattr(
        self.physical_field_chain_measurement,
        'physical_closure_verified',
        False,
      )
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep this research handoff out of product promotion."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """A local candidate and its continuation are never production evidence."""

    return False
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    return False
  ####

  @property
  def canonical_euler_verified(self) -> bool:
    return False
  ####

  @property
  def external_validation_verified(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    def report(value: Any | None) -> dict[str, Any] | None:
      return None if value is None else value.as_report()

    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'resolved': self.resolved,
      'research_audit_accepted': self.research_audit_accepted,
      'cell_count': self.cell_count,
      'continued_cell_count': self.continued_cell_count,
      'first_cell_handoff_verified': self.first_cell_handoff_verified,
      'continued_chain_audit_verified': self.continued_chain_audit_verified,
      'handoff_links_verified': self.handoff_links_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'termination': self.termination.as_report(),
      'candidate': self.candidate.as_report(),
      'candidate_measurement': report(self.candidate_measurement),
      'chain_planner_measurement': report(self.chain_planner_measurement),
      'physical_field_chain_measurement': report(
        self.physical_field_chain_measurement
      ),
      'research_chain_measurement': report(self.research_chain_measurement),
      'physical_field_count': len(self.physical_fields),
      'chain_planner': (
        None if self.chain_planner is None else self.chain_planner.as_report()
      ),
      'diagnostics': dict(self.diagnostics),
    }
  ####


def _chain_planner_termination(
  planner: MocChainPlannerResult,
) -> MocChainTerminationDecision:
  """Convert a completed planner trace into its typed final decision."""

  return MocChainTerminationDecision(
    physical_termination=planner.chain.physical_termination,
    reason=planner.chain.termination_reason,
    message=planner.chain.message,
    diagnostics=dict(planner.chain.diagnostics),
  )


def _research_chain_solver_failure(
  error: Exception,
) -> MocChainTerminationDecision:
  """Return a typed non-physical stop for a failed research handoff."""

  reason = (
    MocChainTerminationReason.INVALID_INPUT
    if isinstance(error, (TypeError, ValueError))
    else MocChainTerminationReason.SOLVER_ERROR
  )
  return MocChainTerminationDecision(
    physical_termination=False,
    reason=reason,
    message=f'first-cell research-chain planner failed before continuation: {error}',
    diagnostics={
      'continued_cell_callback_invoked': False,
      'solver_error': type(error).__name__,
    },
  )


def plan_first_cell_geometry_owned_research_chain(
  candidate: MocFirstCellCandidateResult,
  *,
  start_x_m: float,
  end_x_m: float,
  reference: MocTerminalReflectionPatchAmbientClosureChainReference | None = None,
  mock: MocPrescribedAmbientClosedPostShockChainMock | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocFirstCellResearchChainPlannerResult:
  """Exercise a continued chain from a locally closed first-cell candidate.

  The default path uses the solver-generated reflected terminal-patch
  remesher.  Supplying ``mock`` selects the prescribed next-shock planner
  instead.  These are intentionally research adapters: the first-cell
  candidate must pass its independent local audit, but its canonical,
  Euler/free-boundary, external-validation, and product gates remain closed.
  """

  if not isinstance(candidate, MocFirstCellCandidateResult):
    raise TypeError('candidate must be a MocFirstCellCandidateResult')
  if reference is not None and not isinstance(
    reference,
    MocTerminalReflectionPatchAmbientClosureChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocTerminalReflectionPatchAmbientClosureChainReference or None'
    )
  if mock is not None and not isinstance(
    mock,
    MocPrescribedAmbientClosedPostShockChainMock,
  ):
    raise TypeError(
      'mock must be a MocPrescribedAmbientClosedPostShockChainMock or None'
    )
  if reference is not None and mock is not None:
    raise ValueError('reference and mock are mutually exclusive')

  planner_kind = (
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
    if mock is not None
    else MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  )
  continuation_model = (
    'prescribed-ambient-closed-post-shock-chain-mock'
    if mock is not None
    else 'terminal-reflection-patch-ambient-closure-chain-reference'
  )
  claim_status = (
    'geometry-owned-first-cell-to-prescribed-chain-mock; '
    'canonical-reflected-free-boundary-and-external-validation-pending'
    if mock is not None
    else
    'geometry-owned-first-cell-to-reflected-patch-research-chain; '
    'canonical-reflected-free-boundary-and-external-validation-pending'
  )

  candidate_measurement = None
  measurement_error: str | None = None
  try:
    # Keep validation imports local because validation imports this planner
    # module for its planner-result measurements.
    from exhaust_plume.validation.moc_measurements import (
      measure_first_cell_geometry_owned_candidate,
    )

    candidate_measurement = measure_first_cell_geometry_owned_candidate(candidate)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    measurement_error = str(error)

  candidate_ready = bool(
    candidate.local_physical_closure_verified
    and candidate.field is not None
    and candidate_measurement is not None
    and candidate_measurement.converged
    and candidate_measurement.physical_closure_verified
    and candidate_measurement.chain_promotion_blocked
    and candidate_measurement.production_claim_allowed is False
  )
  fields: list[MocPhysicalPostShockFieldResult] = []
  if candidate.field is not None:
    fields.append(candidate.field)
  diagnostics: dict[str, Any] = {
    'planner_model': 'first-cell-geometry-owned-research-chain',
    'continuation_model': continuation_model,
    'first_cell_source': 'geometry-owned-candidate-local-physical-field',
    'candidate_local_physical_closure_verified': (
      candidate.local_physical_closure_verified
    ),
    'candidate_independent_measurement_verified': (
      False if candidate_measurement is None else candidate_measurement.converged
    ),
    'candidate_measurement_error': measurement_error,
    'continued_cell_callback_invoked': False,
    'canonical_free_boundary_verified': False,
    'canonical_euler_verified': False,
    'external_validation_verified': False,
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
    'fidelity_boundary': (
      'research-only local first-cell handoff; no basic/reduced-provider '
      'promotion'
    ),
  }

  if not candidate_ready:
    diagnostics.update({
      'handoff_blocked_before_continuation': True,
      'handoff_block_reason': (
        'candidate local field or independent first-cell measurement did not '
        'pass'
      ),
    })
    return MocFirstCellResearchChainPlannerResult(
      candidate=candidate,
      chain_planner=None,
      termination=candidate.as_chain_termination_decision(),
      planner_kind=planner_kind,
      claim_status=claim_status,
      physical_fields=tuple(fields),
      candidate_measurement=candidate_measurement,
      diagnostics=diagnostics,
    )

  assert candidate.field is not None

  def observe(
    solved: MocPhysicalPostShockFieldContinuationSolve,
    _current: MocChainCell,
  ) -> None:
    fields.append(solved.field)
    diagnostics['continued_cell_callback_invoked'] = True

  try:
    if mock is not None:
      planner = plan_prescribed_ambient_closed_post_shock_chain_mock(
        candidate.field,
        start_x_m=start_x_m,
        end_x_m=end_x_m,
        mock=mock,
        policy=policy,
        _field_observer=observe,
      )
    else:
      planner = plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure(
        candidate.field,
        start_x_m=start_x_m,
        end_x_m=end_x_m,
        reference=reference,
        policy=policy,
        _field_observer=observe,
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    termination = _research_chain_solver_failure(error)
    diagnostics.update({
      'handoff_blocked_before_continuation': False,
      'continuation_solver_failure': str(error),
      'continued_field_count': len(fields),
    })
    return MocFirstCellResearchChainPlannerResult(
      candidate=candidate,
      chain_planner=None,
      termination=termination,
      planner_kind=planner_kind,
      claim_status=claim_status,
      physical_fields=tuple(fields),
      candidate_measurement=candidate_measurement,
      diagnostics=diagnostics,
    )

  termination = _chain_planner_termination(planner)
  diagnostics.update({
    'handoff_blocked_before_continuation': False,
    'continued_field_count': len(fields),
    'continued_cell_count': planner.chain.cell_count - 1,
    'chain_termination_reason': planner.chain.termination_reason.value,
    'chain_physical_termination': planner.chain.physical_termination,
    'first_cell_field_identity_verified': bool(
      fields and fields[0] is candidate.field
    ),
  })

  chain_planner_measurement = None
  physical_field_chain_measurement = None
  research_chain_measurement = None
  try:
    from exhaust_plume.validation.moc_measurements import (
      measure_first_cell_geometry_owned_research_chain,
    )

    research_chain_measurement = measure_first_cell_geometry_owned_research_chain(
      candidate,
      planner,
      tuple(fields),
    )
    chain_planner_measurement = (
      research_chain_measurement.chain_planner_measurement
    )
    physical_field_chain_measurement = (
      research_chain_measurement.physical_field_chain_measurement
    )
    candidate_measurement = research_chain_measurement.candidate_measurement
    diagnostics.update({
      'research_chain_measurement_status': research_chain_measurement.status.value,
      'research_chain_measurement_converged': research_chain_measurement.converged,
    })
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    diagnostics['research_chain_measurement_error'] = str(error)

  return MocFirstCellResearchChainPlannerResult(
    candidate=candidate,
    chain_planner=planner,
    termination=termination,
    planner_kind=planner_kind,
    claim_status=claim_status,
    physical_fields=tuple(fields),
    candidate_measurement=candidate_measurement,
    chain_planner_measurement=chain_planner_measurement,
    physical_field_chain_measurement=physical_field_chain_measurement,
    research_chain_measurement=research_chain_measurement,
    diagnostics=diagnostics,
  )
####


def plan_first_cell_geometry_owned_alternating_research_chain(
  candidate: MocFirstCellCandidateResult,
  *,
  start_x_m: float,
  end_x_m: float,
  compression_amplitude_rad: float = 1.0e-2,
  source_sample_count: int = 6,
  total_cell_count: int = 3,
  use_trace_referenced_profile: bool = False,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  attachment_angle_half_width_rad: float = 1.0e-6,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  policy: MocChainContinuationPolicy | None = None,
) -> MocFirstCellResearchChainPlannerResult:
  """Continue a geometry-owned candidate with fresh alternating source bands.

  This is the higher-fidelity sibling of
  :func:`plan_first_cell_geometry_owned_research_chain`.  It derives the first
  ``C-``/``C+`` source band from the candidate's accepted shock/ambient trace,
  then derives a fresh band from each accepted downstream field.  The local
  shock solve still uses the explicit compression envelope, so this remains a
  research chain and cannot raise the candidate's canonical, Euler, external,
  or product claims.

  ``end_x_m`` is the chain interface/spacing anchor supplied to the continued
  planner.  It must leave the first reflected source band downstream of that
  interface; no source extrapolation or backtracking is performed when it does
  not.
  """

  if not isinstance(candidate, MocFirstCellCandidateResult):
    raise TypeError('candidate must be a MocFirstCellCandidateResult')

  candidate_measurement = None
  measurement_error: str | None = None
  try:
    from exhaust_plume.validation.moc_measurements import (
      measure_first_cell_geometry_owned_candidate,
    )

    candidate_measurement = measure_first_cell_geometry_owned_candidate(candidate)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    measurement_error = str(error)

  candidate_ready = bool(
    candidate.local_physical_closure_verified
    and candidate.field is not None
    and candidate_measurement is not None
    and candidate_measurement.converged
    and candidate_measurement.physical_closure_verified
    and candidate_measurement.chain_promotion_blocked
    and candidate_measurement.production_claim_allowed is False
  )
  fields: list[MocPhysicalPostShockFieldResult] = []
  if candidate.field is not None:
    fields.append(candidate.field)
  claim_status = (
    'geometry-owned-first-cell-to-alternating-reflected-domain-research-chain; '
    'canonical-reflected-free-boundary-and-external-validation-pending'
  )
  diagnostics: dict[str, Any] = {
    'planner_model': 'first-cell-geometry-owned-alternating-research-chain',
    'continuation_model': (
      'fresh-alternating-reflected-domain-source-band-per-accepted-cell'
    ),
    'first_cell_source': 'geometry-owned-candidate-local-physical-field',
    'candidate_local_physical_closure_verified': (
      candidate.local_physical_closure_verified
    ),
    'candidate_independent_measurement_verified': (
      False if candidate_measurement is None else candidate_measurement.converged
    ),
    'candidate_measurement_error': measurement_error,
    'continued_cell_callback_invoked': False,
    'canonical_free_boundary_verified': False,
    'canonical_euler_verified': False,
    'external_validation_verified': False,
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
    'fidelity_boundary': (
      'higher-fidelity research-only alternating reflected-domain handoff; '
      'no basic/reduced-provider promotion'
    ),
    'source_band_freshness_policy': (
      'fresh-solver-generated-alternating-band-and-exact-incoming-handoff-'
      'required-per-cell'
    ),
    'configured_total_cell_count': total_cell_count,
  }

  if not candidate_ready:
    diagnostics.update({
      'handoff_blocked_before_continuation': True,
      'handoff_block_reason': (
        'candidate local field or independent first-cell measurement did not '
        'pass'
      ),
    })
    return MocFirstCellResearchChainPlannerResult(
      candidate=candidate,
      chain_planner=None,
      termination=candidate.as_chain_termination_decision(),
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=claim_status,
      physical_fields=tuple(fields),
      candidate_measurement=candidate_measurement,
      diagnostics=diagnostics,
    )

  assert candidate.field is not None

  def observe(
    solved: MocPhysicalPostShockFieldContinuationSolve,
    _current: MocChainCell,
  ) -> None:
    fields.append(solved.field)
    diagnostics['continued_cell_callback_invoked'] = True

  try:
    planner = plan_reflected_domain_alternating_source_chain_from_physical_field(
      candidate.field,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      compression_amplitude_rad=compression_amplitude_rad,
      source_sample_count=source_sample_count,
      total_cell_count=total_cell_count,
      use_trace_referenced_profile=use_trace_referenced_profile,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      attachment_angle_half_width_rad=attachment_angle_half_width_rad,
      sample_count=sample_count,
      branch=branch,
      policy=policy,
      _field_observer=observe,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    termination = _research_chain_solver_failure(error)
    diagnostics.update({
      'handoff_blocked_before_continuation': False,
      'continuation_solver_failure': str(error),
      'continued_field_count': len(fields),
    })
    return MocFirstCellResearchChainPlannerResult(
      candidate=candidate,
      chain_planner=None,
      termination=termination,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=claim_status,
      physical_fields=tuple(fields),
      candidate_measurement=candidate_measurement,
      diagnostics=diagnostics,
    )

  termination = _chain_planner_termination(planner)
  diagnostics.update({
    'handoff_blocked_before_continuation': False,
    'continued_field_count': len(fields),
    'continued_cell_count': planner.chain.cell_count - 1,
    'chain_termination_reason': planner.chain.termination_reason.value,
    'chain_physical_termination': planner.chain.physical_termination,
    'first_cell_field_identity_verified': bool(
      fields and fields[0] is candidate.field
    ),
    'alternating_source_chain_planner': dict(planner.diagnostics),
  })

  chain_planner_measurement = None
  physical_field_chain_measurement = None
  research_chain_measurement = None
  try:
    from exhaust_plume.validation.moc_measurements import (
      measure_first_cell_geometry_owned_research_chain,
    )

    research_chain_measurement = measure_first_cell_geometry_owned_research_chain(
      candidate,
      planner,
      tuple(fields),
    )
    chain_planner_measurement = (
      research_chain_measurement.chain_planner_measurement
    )
    physical_field_chain_measurement = (
      research_chain_measurement.physical_field_chain_measurement
    )
    candidate_measurement = research_chain_measurement.candidate_measurement
    diagnostics.update({
      'research_chain_measurement_status': research_chain_measurement.status.value,
      'research_chain_measurement_converged': research_chain_measurement.converged,
    })
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    diagnostics['research_chain_measurement_error'] = str(error)

  return MocFirstCellResearchChainPlannerResult(
    candidate=candidate,
    chain_planner=planner,
    termination=termination,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=claim_status,
    physical_fields=tuple(fields),
    candidate_measurement=candidate_measurement,
    chain_planner_measurement=chain_planner_measurement,
    physical_field_chain_measurement=physical_field_chain_measurement,
    research_chain_measurement=research_chain_measurement,
    diagnostics=diagnostics,
  )
####


def _plan_ambient_closed_post_shock_terminal_patch_chain(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  target_centerline_y_m: float,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None,
  downstream_flow_angle_rad: float | None,
  sample_count: int,
  branch: ShockBranch,
  trace_position_tolerance_m: float,
  seam_position_tolerance_m: float,
  position_tolerance_m: float,
  invariant_tolerance: float,
  shock_angle_tolerance_rad: float,
  maximum_segment_iterations: int,
  policy: MocChainContinuationPolicy | None,
  claim_status: str,
) -> tuple[
  MocChainPlannerResult,
  MocPhysicalPostShockTerminalPatchTransitionResult | None,
]:
  """Capture one terminal-patch transition while planning its chain prefix."""

  transition: MocPhysicalPostShockTerminalPatchTransitionResult | None = None
  invoked = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocChainTerminationDecision:
    nonlocal invoked, transition
    if invoked:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'terminal-patch physical-field planner is intentionally limited to '
          'one continued shock transition'
        ),
      )
    invoked = True
    transition = solve_ambient_closed_post_shock_terminal_patch_transition(
      current,
      next_cell_index,
      incoming_handoff,
      seed,
      end_x_m=terminal_end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      trace_position_tolerance_m=trace_position_tolerance_m,
      seam_position_tolerance_m=seam_position_tolerance_m,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    return transition.decision

  return (
    plan_ambient_closed_post_shock_chain(
      seed,
      solve_next,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      policy=policy,
      require_upstream_shock_coupling=True,
      claim_status=claim_status,
    ),
    transition,
  )


def plan_ambient_closed_post_shock_chain_terminal_patch(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-3,
  seam_position_tolerance_m: float = 3.0e-3,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Plan one reflected physical-field transition into a typed terminal.

  The seed's ``end_x_m`` is the shared axial interface for the accepted first
  cell.  ``terminal_end_x_m`` is a separate bound for the continued shock
  attempt because the derived terminal reflection patch begins at the outer
  end of the seed's carried trace.  Keeping those coordinates separate makes
  the physical handoff explicit and prevents a planner bookkeeping endpoint
  from silently becoming a solved shock boundary.

  This planner is intentionally one transition deep.  If the downstream
  marcher does not reach a verified normal-shock terminal, the callback
  returns a typed non-physical stop and the planner retains only the accepted
  seed cell.  No open patch, reduced-order cell, or unresolved subsonic field
  is appended to the resolved chain.
  """

  resolved_claim_status = (
    'ambient-closed-field-terminal-reflection-patch; '
    'typed-normal-shock-stop; mixed-regime-cell-promotion-pending'
    if claim_status is None
    else claim_status
  )
  planner, _ = _plan_ambient_closed_post_shock_terminal_patch_chain(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    trace_position_tolerance_m=trace_position_tolerance_m,
    seam_position_tolerance_m=seam_position_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
    claim_status=resolved_claim_status,
  )
  return replace(
    planner,
    diagnostics={
      'transition_model': (
        'accepted-ambient-closed-field -> open-shock-ambient-strip -> '
        'centerline-reflection-patch -> attached-shock -> normal-shock-terminal'
      ),
      'terminal_patch_planner_depth': 1,
      'terminal_end_x_m': float(terminal_end_x_m),
      'target_centerline_y_m': float(target_centerline_y_m),
      'downstream_flow_angle_model': (
        'callback-supplied'
        if downstream_flow_angle_at is not None
        else 'constant-research-angle'
      ),
      'downstream_flow_angle_rad': downstream_flow_angle_rad,
      'sample_count': sample_count,
      'branch': branch.value,
      'trace_position_tolerance_m': float(trace_position_tolerance_m),
      'seam_position_tolerance_m': float(seam_position_tolerance_m),
      'position_tolerance_m': float(position_tolerance_m),
      'invariant_tolerance': float(invariant_tolerance),
      'shock_angle_tolerance_rad': float(shock_angle_tolerance_rad),
      'production_claim_allowed': False,
      'physical_cell_promotion': 'blocked-at-mixed-regime-boundary',
    },
  )
####


def plan_ambient_closed_post_shock_chain_terminal_patch_with_mixed_regime(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-3,
  seam_position_tolerance_m: float = 3.0e-3,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
  solve_field: Callable[
    [MocMixedRegimePerimeterRequest],
    MocMixedRegimeFieldResult | None,
  ] | None = None,
  control_section: MocMixedRegimeControlSection | None = None,
  use_integrated_flux: bool = False,
  attach_mixed_regime_field: bool = False,
  free_boundary_refinement_sample_counts: Sequence[int] | None = None,
  mixed_regime_entropy_source_arc_length_m: Sequence[float] | None = None,
  mixed_regime_entropy_streamline_ids: Sequence[int] | None = None,
  claim_status: str | None = None,
) -> MocPhysicalPostShockTerminalPatchPlannerResult:
  """Plan the terminal transition and exercise its exact mixed-regime seam.

  The chain portion is the same one-step terminal-patch planner used by the
  supersonic lane.  Once that transition reaches a typed normal-shock stop,
  the retained request is sent to exactly one explicitly selected downstream
  mode: the default prescribed mock, the solver-owned scalar free-boundary
  reference, or a caller-supplied mixed-regime field callback.  The returned
  mixed-regime result is evidence beside the chain by default.  Callers may
  explicitly set ``attach_mixed_regime_field`` to retain a field on the
  terminal transition after the exact seam checks pass; that still never
  creates a new supersonic cell or raises the production claim ceiling.
  ``free_boundary_refinement_sample_counts`` optionally reruns the
  solver-owned reference at increasing perimeter resolutions and records the
  independent refinement measurement; it is valid only with ``solver``.
  ``control_section`` is accepted only with ``solver``.  The default section
  mode requires terminal-equivalent scalar states; ``use_integrated_flux``
  selects the explicitly named distributed-flux quasi-one-dimensional
  reference for a varying section.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  if mock is not None and not isinstance(
    mock,
    MocPrescribedMixedRegimeClosureMock,
  ):
    raise TypeError(
      'mock must be a MocPrescribedMixedRegimeClosureMock or None'
    )
  if solver is not None and not isinstance(
    solver,
    MocSolverGeneratedMixedRegimeClosureReference,
  ):
    raise TypeError(
      'solver must be a MocSolverGeneratedMixedRegimeClosureReference or None'
    )
  if solve_field is not None and not callable(solve_field):
    raise TypeError('solve_field must be callable when supplied')
  if control_section is not None and not isinstance(
    control_section,
    MocMixedRegimeControlSection,
  ):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection or None'
    )
  if control_section is not None and solver is None:
    raise ValueError('control_section requires the solver-generated reference')
  if not isinstance(use_integrated_flux, bool):
    raise TypeError('use_integrated_flux must be a bool')
  if use_integrated_flux and control_section is None:
    raise ValueError('use_integrated_flux requires a control_section')
  if use_integrated_flux and solver is None:
    raise ValueError('use_integrated_flux requires the solver-generated reference')
  if control_section is not None and (mock is not None or solve_field is not None):
    raise ValueError('control_section is supported only by the solver-generated reference')
  if not isinstance(attach_mixed_regime_field, bool):
    raise TypeError('attach_mixed_regime_field must be a bool')
  if (
    mixed_regime_entropy_source_arc_length_m is None
  ) != (
    mixed_regime_entropy_streamline_ids is None
  ):
    raise ValueError(
      'mixed_regime_entropy_source_arc_length_m and '
      'mixed_regime_entropy_streamline_ids must be supplied together'
    )
  refinement_counts: tuple[int, ...] = ()
  if free_boundary_refinement_sample_counts is not None:
    if solver is None:
      raise ValueError(
        'free-boundary refinement sample counts require the solver-owned '
        'mixed-regime reference'
      )
    try:
      refinement_counts = tuple(free_boundary_refinement_sample_counts)
    except TypeError as error:
      raise TypeError(
        'free_boundary_refinement_sample_counts must be an iterable of '
        'integers'
      ) from error
    if len(refinement_counts) < 2:
      raise ValueError(
        'free_boundary refinement requires at least two sample counts'
      )
    if any(
      isinstance(count, bool) or not isinstance(count, int) or count < 3
      for count in refinement_counts
    ):
      raise ValueError(
        'free boundary refinement sample counts must be integers of at least '
        'three'
      )
    if any(
      right <= left
      for left, right in zip(refinement_counts, refinement_counts[1:])
    ):
      raise ValueError(
        'free boundary refinement sample counts must increase strictly'
      )
  supplied_modes = sum(
    value is not None for value in (mock, solver, solve_field)
  )
  if supplied_modes > 1:
    raise ValueError('supply only one of mock, solver, or solve_field')
  if supplied_modes == 0:
    mock = MocPrescribedMixedRegimeClosureMock()

  planner_kind = (
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
    if mock is not None
    else MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  )
  default_claim = (
    'continued-terminal-patch-planner-mixed-regime; '
    'typed-normal-shock-stop; canonical-mixed-regime-free-boundary-pending'
  )
  chain_planner, transition = _plan_ambient_closed_post_shock_terminal_patch_chain(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    trace_position_tolerance_m=trace_position_tolerance_m,
    seam_position_tolerance_m=seam_position_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
    claim_status=default_claim if claim_status is None else claim_status,
  )

  mixed_regime_closure: MocMixedRegimeClosureResult | None = None
  mixed_regime_reference: MocMixedRegimeFreeBoundaryResult | None = None
  mixed_regime_entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None
  diagnostics: dict[str, Any] = {
    'planner_model': 'ambient-closed-field-terminal-patch-mixed-regime-planner',
    'transition_model': (
      'accepted-ambient-closed-field -> open-shock-ambient-strip -> '
      'centerline-reflection-patch -> attached-shock -> normal-shock-terminal'
    ),
    'terminal_patch_planner_depth': 1,
    'terminal_end_x_m': float(terminal_end_x_m),
    'target_centerline_y_m': float(target_centerline_y_m),
    'downstream_flow_angle_model': (
      'callback-supplied'
      if downstream_flow_angle_at is not None
      else 'constant-research-angle'
    ),
    'downstream_flow_angle_rad': downstream_flow_angle_rad,
    'sample_count': sample_count,
    'branch': branch.value,
    'trace_position_tolerance_m': float(trace_position_tolerance_m),
    'seam_position_tolerance_m': float(seam_position_tolerance_m),
    'position_tolerance_m': float(position_tolerance_m),
    'invariant_tolerance': float(invariant_tolerance),
    'shock_angle_tolerance_rad': float(shock_angle_tolerance_rad),
    'mixed_regime_solver_supplied': supplied_modes == 1,
    'mixed_regime_closure_attached': False,
    'mixed_regime_entropy_handoff_requested': False,
    'mixed_regime_entropy_handoff_verified': False,
    'mixed_regime_entropy_handoff_measurement': None,
    'mixed_regime_field_attachment_requested': attach_mixed_regime_field,
    'terminal_closure_audit': None,
    'terminal_closure_audit_accepted': False,
    'terminal_supersonic_audit_accepted': False,
    'free_boundary_reference_audit': None,
    'free_boundary_reference_audit_accepted': False,
    'free_boundary_refinement_sample_counts': (
      list(refinement_counts) if refinement_counts else None
    ),
    'free_boundary_refinement': None,
    'free_boundary_refinement_accepted': False,
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
  }
  if mock is not None:
    diagnostics['mixed_regime_solver_mode'] = 'prescribed-boundary-mock'
    diagnostics['prescribed_mixed_regime_closure_mock'] = mock.as_report()
  elif solver is not None:
    diagnostics['mixed_regime_solver_mode'] = 'solver-generated-reference'
    diagnostics['solver_generated_mixed_regime_reference'] = solver.as_report()
    diagnostics['control_section_supplied'] = control_section is not None
    diagnostics['control_section_flux_mode'] = (
      'integrated-flux-quasi-1d-reference'
      if use_integrated_flux
      else 'terminal-equivalent-geometric-measure'
    )
    if control_section is not None:
      diagnostics['control_section'] = control_section.as_report()
  else:
    diagnostics['mixed_regime_solver_mode'] = 'caller-supplied-field'

  if transition is None:
    diagnostics['mixed_regime_solver_skipped'] = (
      'the chain planner did not invoke the terminal transition'
    )
  elif transition.mixed_regime_request is None:
    diagnostics['mixed_regime_solver_skipped'] = (
      'terminal transition did not produce a complete mixed-regime seam'
    )
    diagnostics['transition_report'] = transition.as_report()
  else:
    request = transition.as_mixed_regime_perimeter_request()
    diagnostics['mixed_regime_entropy_handoff_requested'] = True
    (
      mixed_regime_entropy_handoff,
      entropy_measurement,
      entropy_verified,
      entropy_error,
    ) = _audit_mixed_regime_entropy_handoff(request)
    if entropy_measurement is not None:
      diagnostics['mixed_regime_entropy_handoff_measurement'] = (
        entropy_measurement
      )
    diagnostics['mixed_regime_entropy_handoff_verified'] = entropy_verified
    if entropy_error is not None:
      diagnostics['mixed_regime_entropy_handoff_error'] = entropy_error
    if mixed_regime_entropy_handoff is not None:
      diagnostics['mixed_regime_entropy_handoff'] = (
        mixed_regime_entropy_handoff.as_report()
      )
    try:
      if mock is not None:
        mixed_regime_closure = mock.solve(request)
      elif solver is not None:
        mixed_regime_reference = (
          solver.solve_from_control_section_flux(request, control_section)
          if use_integrated_flux
          else solver.solve_from_control_section(request, control_section)
          if control_section is not None
          else solver.solve(request)
        )
        mixed_regime_closure = mixed_regime_reference.closure
      else:
        assert solve_field is not None
        mixed_regime_closure = run_mixed_regime_closure_solver(
          request,
          solve_field,
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      diagnostics['mixed_regime_solver_error'] = str(error)
    else:
      diagnostics['mixed_regime_closure_status'] = (
        mixed_regime_closure.status.value
        if mixed_regime_closure is not None
        else 'solver-owned-reference-no-closure'
      )
      diagnostics['mixed_regime_model_closure_verified'] = bool(
        mixed_regime_closure is not None
        and mixed_regime_closure.converged
        and mixed_regime_closure.physical_closure_verified
      )
      if mixed_regime_reference is not None:
        diagnostics['solver_generated_mixed_regime_result'] = (
          mixed_regime_reference.as_report()
        )
      if mixed_regime_closure is not None and not mixed_regime_closure.converged:
        diagnostics['mixed_regime_closure_message'] = (
          mixed_regime_closure.message
        )

      terminal_closure_audit_accepted = False
      terminal_supersonic_audit_accepted = False
      if transition.terminal_field is not None:
        try:
          # Keep validation imports local: validation imports the model
          # package, while this planner is imported during package startup.
          from exhaust_plume.validation.moc_measurements import (
            MocTerminalClosureObservation,
            measure_moc_terminal_closure,
          )

          terminal_closure_measurement = measure_moc_terminal_closure(
            MocTerminalClosureObservation(
              terminal_field=transition.terminal_field,
              mixed_regime_closure=mixed_regime_closure,
            )
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
          diagnostics['terminal_closure_audit_error'] = str(error)
        else:
          diagnostics['terminal_closure_audit'] = (
            terminal_closure_measurement.as_report()
          )
          terminal_closure_audit_accepted = bool(
            terminal_closure_measurement.converged
            and terminal_closure_measurement.physical_closure_verified
            and terminal_closure_measurement.physical_termination_verified
            and terminal_closure_measurement.chain_promotion_blocked
          )
          terminal_supersonic_audit_accepted = bool(
            terminal_closure_measurement.terminal_normal_shock_verified
            and terminal_closure_measurement.terminal_shock_geometry_verified
            and terminal_closure_measurement.terminal_pressure_loss_verified
            and terminal_closure_measurement.supersonic_patch_verified
            and terminal_closure_measurement.chain_promotion_blocked
          )
          diagnostics['terminal_supersonic_audit_accepted'] = (
            terminal_supersonic_audit_accepted
          )
          diagnostics['terminal_closure_audit_accepted'] = (
            terminal_closure_audit_accepted
          )
      else:
        diagnostics['terminal_closure_audit_skipped'] = (
          'terminal transition did not retain a terminal supersonic field'
        )

      free_boundary_reference_audit_accepted = False
      if mixed_regime_reference is not None:
        try:
          from exhaust_plume.validation.moc_measurements import (
            measure_mixed_regime_free_boundary_reference,
          )

          free_boundary_measurement = (
            measure_mixed_regime_free_boundary_reference(
              mixed_regime_reference,
            )
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
          diagnostics['free_boundary_reference_audit_error'] = str(error)
        else:
          diagnostics['free_boundary_reference_audit'] = (
            free_boundary_measurement.as_report()
          )
          free_boundary_reference_audit_accepted = bool(
            free_boundary_measurement.converged
            and free_boundary_measurement.physical_closure_verified
            and free_boundary_measurement.chain_promotion_blocked
            and not free_boundary_measurement.production_claim_allowed
          )
          diagnostics['free_boundary_reference_audit_accepted'] = (
            free_boundary_reference_audit_accepted
          )
          diagnostics['terminal_closure_audit_accepted'] = bool(
            terminal_supersonic_audit_accepted
            and free_boundary_reference_audit_accepted
          )
          if refinement_counts:
            try:
              assert solver is not None
              from exhaust_plume.validation.moc_measurements import (
                MocMixedRegimeFreeBoundaryRefinementCase,
                measure_mixed_regime_free_boundary_refinement,
              )

              refinement_cases = tuple(
                MocMixedRegimeFreeBoundaryRefinementCase(
                  resolution=count,
                  result=(
                    replace(solver, free_boundary_sample_count=count)
                    .solve_from_control_section_flux(request, control_section)
                    if use_integrated_flux
                    else replace(solver, free_boundary_sample_count=count)
                    .solve_from_control_section(request, control_section)
                    if control_section is not None
                    else replace(solver, free_boundary_sample_count=count)
                    .solve(request)
                  ),
                )
                for count in refinement_counts
              )
              refinement_measurement = (
                measure_mixed_regime_free_boundary_refinement(
                  refinement_cases,
                )
              )
            except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
              diagnostics['free_boundary_refinement_error'] = str(error)
            else:
              diagnostics['free_boundary_refinement'] = (
                refinement_measurement.as_report()
              )
              diagnostics['free_boundary_refinement_accepted'] = bool(
                refinement_measurement.converged
                and refinement_measurement.chain_promotion_blocked
                and not refinement_measurement.production_claim_allowed
              )
      if (
        attach_mixed_regime_field
        and mixed_regime_closure is not None
        and mixed_regime_closure.converged
        and mixed_regime_closure.field is not None
        and terminal_closure_audit_accepted
        and (
          mixed_regime_reference is None
          or free_boundary_reference_audit_accepted
        )
      ):
        try:
          transition = transition.attach_mixed_regime_closure(
            mixed_regime_closure
          )
        except (TypeError, ValueError) as error:
          diagnostics['mixed_regime_field_attachment_error'] = str(error)
        else:
          diagnostics['mixed_regime_closure_attached'] = True
          diagnostics['mixed_regime_field_attached'] = True
          diagnostics['mixed_regime_field_complete'] = (
            transition.mixed_regime_field_complete
          )

  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None
  if mixed_regime_entropy_source_arc_length_m is not None:
    if mixed_regime_entropy_handoff is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'entropy handoff was not available for the explicit source map'
      )
    elif mixed_regime_closure is None or mixed_regime_closure.field is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'mixed-regime solver did not return a scalar field for the explicit '
        'source map'
      )
    else:
      (
        mixed_regime_entropy_transport,
        transport_measurement,
        transport_verified,
        transport_error,
      ) = _audit_mixed_regime_entropy_transport(
        transition.mixed_regime_request,
        mixed_regime_entropy_handoff,
        mixed_regime_closure.field,
        mixed_regime_entropy_source_arc_length_m,
        mixed_regime_entropy_streamline_ids or (),
      )
      diagnostics['mixed_regime_entropy_transport_verified'] = (
        transport_verified
      )
      if transport_measurement is not None:
        diagnostics['mixed_regime_entropy_transport_measurement'] = (
          transport_measurement
        )
      if transport_error is not None:
        diagnostics['mixed_regime_entropy_transport_error'] = transport_error
      if mixed_regime_entropy_transport is not None:
        diagnostics['mixed_regime_entropy_transport'] = (
          mixed_regime_entropy_transport.as_report()
        )

  return MocPhysicalPostShockTerminalPatchPlannerResult(
    chain_planner=chain_planner,
    transition=transition,
    mixed_regime_closure=mixed_regime_closure,
    mixed_regime_reference=mixed_regime_reference,
    planner_kind=planner_kind,
    claim_status=(
      default_claim if claim_status is None else claim_status
    ),
    diagnostics=diagnostics,
    mixed_regime_entropy_handoff=mixed_regime_entropy_handoff,
    mixed_regime_entropy_transport=mixed_regime_entropy_transport,
  )
####


def plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure_with_planar_handoff(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  solve_field: MocMixedRegimePlanarFieldSolver,
  reference: MocTerminalReflectionPatchAmbientClosureChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  terminal_policy: MocChainContinuationPolicy | None = None,
  planar_position_tolerance_m: float = 1.0e-10,
  planar_state_tolerance: float = 1.0e-8,
  planar_pressure_tolerance: float = 1.0e-8,
  planar_normal_flux_tolerance: float = 1.0e-8,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
) -> MocAmbientClosedPostShockChainTerminalPlannerResult:
  """Continue a reflected prefix, then audit an explicit planar handoff.

  The accepted supersonic prefix and the downstream callback remain separate
  results.  The callback receives the exact terminal request generated from
  the final carried field, while its scalar control section and perimeter are
  caller-owned inputs.  A passing handoff is research evidence only: it is
  not appended as a shock cell and cannot promote a product/provider claim.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    raise TypeError('seed must be a MocPhysicalPostShockFieldResult')
  fixture = (
    MocTerminalReflectionPatchAmbientClosureChainReference()
    if reference is None
    else reference
  )
  if not isinstance(
    fixture,
    MocTerminalReflectionPatchAmbientClosureChainReference,
  ):
    raise TypeError(
      'reference must be a '
      'MocTerminalReflectionPatchAmbientClosureChainReference'
    )
  if policy is not None and not isinstance(policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')
  if terminal_policy is not None and not isinstance(
    terminal_policy,
    MocChainContinuationPolicy,
  ):
    raise TypeError(
      'terminal_policy must be a MocChainContinuationPolicy or None'
    )
  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  if not callable(solve_field):
    raise TypeError('solve_field must be callable')

  (
    prefix,
    captured_field,
    captured_fields,
    captured_cell_index,
    prefix_cell,
  ) = _capture_terminal_reflection_patch_prefix(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    reference=fixture,
    policy=policy,
  )
  diagnostics: dict[str, Any] = {
    'planner_model': (
      'ambient-closed-post-shock-chain-terminal-reflection-patch-'
      'planar-handoff'
    ),
    'prefix_cell_count': prefix.chain.cell_count,
    'prefix_field_count': len(captured_fields),
    'prefix_planner_kind': prefix.planner_kind.value,
    'prefix_planner_audit': None,
    'prefix_planner_audit_accepted': False,
    'prefix_physical_field_audit': None,
    'prefix_physical_field_audit_accepted': False,
    'terminal_attempted': False,
    'terminal_input_cell_index': (
      None if prefix_cell is None else prefix_cell.cell_index
    ),
    'terminal_input_cell_end_x_m': (
      None if prefix_cell is None else prefix_cell.end_x_m
    ),
    'terminal_end_x_m': float(terminal_end_x_m),
    'mixed_regime_planar_handoff_requested': True,
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_solver_model': str(solver_model),
    'terminal_mixed_regime_field_attached': False,
    'fidelity_boundary': (
      'research-only continued supersonic prefix plus explicit planar '
      'mixed-regime handoff; no basic/reduced-provider promotion'
    ),
    'chain_promotion_blocked': True,
    'production_claim_allowed': False,
  }
  try:
    # Keep validation imports local: validation imports the model package while
    # this planner is imported during package startup.
    from exhaust_plume.validation.moc_measurements import (
      measure_moc_ambient_closed_physical_field_chain,
      measure_moc_chain_planner,
    )

    prefix_planner_measurement = measure_moc_chain_planner(prefix)
    prefix_physical_field_measurement = (
      measure_moc_ambient_closed_physical_field_chain(captured_fields)
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    diagnostics['prefix_audit_error'] = str(error)
  else:
    diagnostics['prefix_planner_audit'] = prefix_planner_measurement.as_report()
    diagnostics['prefix_planner_audit_accepted'] = bool(
      prefix_planner_measurement.converged
      and prefix_planner_measurement.termination_verified
      and prefix_planner_measurement.fidelity_isolation_verified
      and not prefix_planner_measurement.production_claim_allowed
    )
    diagnostics['prefix_physical_field_audit'] = (
      prefix_physical_field_measurement.as_report()
    )
    diagnostics['prefix_physical_field_audit_accepted'] = bool(
      prefix_physical_field_measurement.converged
      and prefix_physical_field_measurement.physical_closure_verified
      and prefix_physical_field_measurement.chain_promotion_blocked
      and not prefix_physical_field_measurement.production_claim_allowed
    )
  if (
    prefix_cell is None
    or captured_field is None
    or captured_cell_index != prefix_cell.cell_index
    or prefix.chain.cell_count < 2
    or prefix.chain.cells[-1].cell_index != prefix.chain.cell_count
  ):
    diagnostics['terminal_attempt_message'] = (
      'continued prefix did not accept a new physical field; planar mixed-'
      'regime handoff was not attempted'
    )
    return MocAmbientClosedPostShockChainTerminalPlannerResult(
      chain_planner=prefix,
      terminal_planner=None,
      planner_kind=prefix.planner_kind,
      claim_status=(
        'continued-terminal-reflection-patch-planar-handoff; terminal-'
        'transition-not-reached; canonical-reflected-free-boundary-and-'
        'external-validation-pending'
      ),
      diagnostics=diagnostics,
    )

  effective_terminal_policy = terminal_policy
  if effective_terminal_policy is None:
    effective_terminal_policy = MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    )
  diagnostics['terminal_attempted'] = True
  terminal = plan_ambient_closed_post_shock_chain_terminal_patch_with_planar_handoff(
    captured_field,
    start_x_m=prefix_cell.start_x_m,
    end_x_m=prefix_cell.end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    control_section=control_section,
    perimeter_spec=perimeter_spec,
    solve_field=solve_field,
    downstream_flow_angle_rad=0.0,
    sample_count=fixture.sample_count,
    branch=fixture.branch,
    trace_position_tolerance_m=fixture.trace_position_tolerance_m,
    seam_position_tolerance_m=fixture.seam_position_tolerance_m,
    position_tolerance_m=fixture.position_tolerance_m,
    invariant_tolerance=fixture.invariant_tolerance,
    shock_angle_tolerance_rad=fixture.shock_angle_tolerance_rad,
    maximum_segment_iterations=fixture.maximum_segment_iterations,
    policy=effective_terminal_policy,
    planar_position_tolerance_m=planar_position_tolerance_m,
    planar_state_tolerance=planar_state_tolerance,
    planar_pressure_tolerance=planar_pressure_tolerance,
    planar_normal_flux_tolerance=planar_normal_flux_tolerance,
    solver_model=solver_model,
  )
  diagnostics.update({
    'terminal_planner_kind': terminal.planner_kind.value,
    'terminal_resolved': terminal.resolved,
    'terminal_physical_termination': terminal.physical_termination,
    'terminal_physical_closure_verified': terminal.physical_closure_verified,
    'terminal_mixed_regime_planar_handoff_verified': (
      terminal.mixed_regime_planar_handoff_verified
    ),
    'terminal_report': terminal.as_report(),
  })
  return MocAmbientClosedPostShockChainTerminalPlannerResult(
    chain_planner=prefix,
    terminal_planner=terminal,
    planner_kind=prefix.planner_kind,
    claim_status=(
      'continued-terminal-reflection-patch-planar-handoff; canonical-'
      'reflected-free-boundary-and-external-validation-pending'
    ),
    diagnostics=diagnostics,
  )
####


def plan_ambient_closed_post_shock_chain_terminal_patch_with_planar_handoff(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  control_section: MocMixedRegimeControlSection,
  perimeter_spec: MocMixedRegimeDownstreamPerimeterSpec,
  solve_field: MocMixedRegimePlanarFieldSolver,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-3,
  seam_position_tolerance_m: float = 3.0e-3,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
  planar_position_tolerance_m: float = 1.0e-10,
  planar_state_tolerance: float = 1.0e-8,
  planar_pressure_tolerance: float = 1.0e-8,
  planar_normal_flux_tolerance: float = 1.0e-8,
  solver_model: str = 'caller-supplied-planar-mixed-regime-solver',
  mixed_regime_entropy_source_arc_length_m: Sequence[float] | None = None,
  mixed_regime_entropy_streamline_ids: Sequence[int] | None = None,
  claim_status: str | None = None,
) -> MocPhysicalPostShockTerminalPatchPlannerResult:
  """Audit a planar downstream callback after the terminal patch transition.

  The terminal transition and the planar callback are deliberately separate
  stages.  The callback receives the exact retained terminal request together
  with caller-owned control-section and perimeter data; a passing handoff is
  recorded beside the one-step chain and never attached as a supersonic cell.
  This gives continued-chain orchestration the same explicit planar seam as
  the first-cell planner without implying that the callback is the canonical
  reflected-MOC/free-boundary solver.
  """

  if not isinstance(control_section, MocMixedRegimeControlSection):
    raise TypeError(
      'control_section must be a MocMixedRegimeControlSection'
    )
  if not isinstance(
    perimeter_spec,
    MocMixedRegimeDownstreamPerimeterSpec,
  ):
    raise TypeError(
      'perimeter_spec must be a MocMixedRegimeDownstreamPerimeterSpec'
    )
  if not callable(solve_field):
    raise TypeError('solve_field must be callable')
  if (
    mixed_regime_entropy_source_arc_length_m is None
  ) != (
    mixed_regime_entropy_streamline_ids is None
  ):
    raise ValueError(
      'mixed_regime_entropy_source_arc_length_m and '
      'mixed_regime_entropy_streamline_ids must be supplied together'
    )

  resolved_claim_status = (
    'continued-terminal-patch-explicit-planar-handoff; canonical-reflected-moc-'
    'free-boundary-and-external-validation-pending'
    if claim_status is None
    else claim_status
  )
  chain_planner, transition = _plan_ambient_closed_post_shock_terminal_patch_chain(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    trace_position_tolerance_m=trace_position_tolerance_m,
    seam_position_tolerance_m=seam_position_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    policy=policy,
    claim_status=resolved_claim_status,
  )
  diagnostics: dict[str, Any] = {
    'planner_model': (
      'ambient-closed-field-terminal-patch-planar-handoff'
    ),
    'transition_model': (
      'accepted-ambient-closed-field -> open-shock-ambient-strip -> '
      'centerline-reflection-patch -> attached-shock -> normal-shock-terminal'
    ),
    'terminal_patch_planner_depth': 1,
    'terminal_end_x_m': float(terminal_end_x_m),
    'target_centerline_y_m': float(target_centerline_y_m),
    'downstream_flow_angle_model': (
      'callback-supplied'
      if downstream_flow_angle_at is not None
      else 'constant-research-angle'
    ),
    'downstream_flow_angle_rad': downstream_flow_angle_rad,
    'sample_count': sample_count,
    'branch': branch.value,
    'trace_position_tolerance_m': float(trace_position_tolerance_m),
    'seam_position_tolerance_m': float(seam_position_tolerance_m),
    'position_tolerance_m': float(position_tolerance_m),
    'invariant_tolerance': float(invariant_tolerance),
    'shock_angle_tolerance_rad': float(shock_angle_tolerance_rad),
    'production_claim_allowed': False,
    'physical_cell_promotion': 'blocked-at-mixed-regime-boundary',
    'chain_promotion_blocked': True,
    'mixed_regime_entropy_handoff_requested': False,
    'mixed_regime_entropy_handoff_verified': False,
    'mixed_regime_entropy_handoff_measurement': None,
    'mixed_regime_entropy_transport_requested': (
      mixed_regime_entropy_source_arc_length_m is not None
    ),
    'mixed_regime_entropy_transport_verified': False,
    'mixed_regime_entropy_transport_measurement': None,
  }
  diagnostics.update({
    'mixed_regime_planar_handoff_requested': True,
    'mixed_regime_planar_handoff_attached': False,
    'mixed_regime_planar_solver_model': solver_model,
  })
  if transition is None or transition.mixed_regime_request is None:
    diagnostics['mixed_regime_planar_handoff_skipped'] = (
      'terminal transition did not produce a complete mixed-regime seam'
    )
    return MocPhysicalPostShockTerminalPatchPlannerResult(
      chain_planner=chain_planner,
      transition=transition,
      mixed_regime_closure=None,
      mixed_regime_reference=None,
      planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
      claim_status=resolved_claim_status,
      diagnostics=diagnostics,
    )

  entropy_handoff, entropy_measurement, entropy_verified, entropy_error = (
    _audit_mixed_regime_entropy_handoff(transition.mixed_regime_request)
  )
  diagnostics['mixed_regime_entropy_handoff_requested'] = True
  diagnostics['mixed_regime_entropy_handoff_verified'] = entropy_verified
  if entropy_measurement is not None:
    diagnostics['mixed_regime_entropy_handoff_measurement'] = (
      entropy_measurement
    )
  if entropy_error is not None:
    diagnostics['mixed_regime_entropy_handoff_error'] = entropy_error
  if entropy_handoff is not None:
    diagnostics['mixed_regime_entropy_handoff'] = entropy_handoff.as_report()

  handoff = run_mixed_regime_planar_field_solver(
    transition.mixed_regime_request,
    control_section,
    perimeter_spec,
    solve_field,
    position_tolerance_m=planar_position_tolerance_m,
    state_tolerance=planar_state_tolerance,
    pressure_tolerance=planar_pressure_tolerance,
    normal_flux_tolerance=planar_normal_flux_tolerance,
    solver_model=solver_model,
  )
  diagnostics.update({
    'mixed_regime_planar_handoff_verified': handoff.handoff_verified,
    'mixed_regime_planar_handoff': handoff.as_report(),
    'mixed_regime_planar_handoff_physical_closure_verified': (
      handoff.physical_closure_verified
    ),
    'mixed_regime_planar_handoff_chain_promotion_blocked': (
      handoff.chain_promotion_blocked
    ),
  })
  mixed_regime_entropy_transport: MocMixedRegimeEntropyTransportResult | None = None
  if mixed_regime_entropy_source_arc_length_m is not None:
    if entropy_handoff is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'entropy handoff was not available for the explicit source map'
      )
    elif handoff.field is None:
      diagnostics['mixed_regime_entropy_transport_skipped'] = (
        'planar handoff did not return a scalar field for the explicit source map'
      )
    else:
      (
        mixed_regime_entropy_transport,
        transport_measurement,
        transport_verified,
        transport_error,
      ) = _audit_mixed_regime_entropy_transport(
        transition.mixed_regime_request,
        entropy_handoff,
        handoff.field,
        mixed_regime_entropy_source_arc_length_m,
        mixed_regime_entropy_streamline_ids or (),
      )
      diagnostics['mixed_regime_entropy_transport_verified'] = (
        transport_verified
      )
      if transport_measurement is not None:
        diagnostics['mixed_regime_entropy_transport_measurement'] = (
          transport_measurement
        )
      if transport_error is not None:
        diagnostics['mixed_regime_entropy_transport_error'] = transport_error
      if mixed_regime_entropy_transport is not None:
        diagnostics['mixed_regime_entropy_transport'] = (
          mixed_regime_entropy_transport.as_report()
        )
  return MocPhysicalPostShockTerminalPatchPlannerResult(
    chain_planner=chain_planner,
    transition=transition,
    mixed_regime_closure=None,
    mixed_regime_reference=None,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=resolved_claim_status,
    diagnostics=diagnostics,
    mixed_regime_planar_handoff=handoff,
    mixed_regime_entropy_handoff=entropy_handoff,
    mixed_regime_entropy_transport=mixed_regime_entropy_transport,
  )
####


def plan_ambient_closed_post_shock_chain_terminal_patch_mock(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  mock: MocPrescribedMixedRegimeClosureMock | None = None,
  **kwargs: Any,
) -> MocPhysicalPostShockTerminalPatchPlannerResult:
  """Run the continued terminal transition through the explicit planner mock."""

  fixture = (
    MocPrescribedMixedRegimeClosureMock() if mock is None else mock
  )
  return plan_ambient_closed_post_shock_chain_terminal_patch_with_mixed_regime(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    mock=fixture,
    **kwargs,
  )
####


def plan_ambient_closed_post_shock_chain_terminal_patch_reference(
  seed: MocPhysicalPostShockFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  terminal_end_x_m: float,
  solver: MocSolverGeneratedMixedRegimeClosureReference | None = None,
  **kwargs: Any,
) -> MocPhysicalPostShockTerminalPatchPlannerResult:
  """Run the continued terminal transition through the scalar reference."""

  reference = (
    MocSolverGeneratedMixedRegimeClosureReference()
    if solver is None else solver
  )
  return plan_ambient_closed_post_shock_chain_terminal_patch_with_mixed_regime(
    seed,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    terminal_end_x_m=terminal_end_x_m,
    solver=reference,
    **kwargs,
  )
####
