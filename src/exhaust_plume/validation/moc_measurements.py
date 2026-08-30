"""Independent geometry measurements for the planar-MOC shock-cell lane.

The MOC solver owns characteristic compatibility and physical closure.  This
module owns a separate, deliberately small measurement operator: it extracts
shock-cell geometry and optional shock total-pressure loss from an assembled
field, while preserving topology and fidelity metadata in the result.  It
does not infer a shock from a scalar trace, fill an open boundary, or promote
the measurement to validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import atan2, cos, fsum, hypot, isfinite, log, pi, sin, sqrt, tan
from typing import Any, Sequence

from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeBoundaryResult,
  MocMixedRegimeControlSection,
  MocMixedRegimeClosureResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionResult,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimeFieldStatus,
  MocMixedRegimeFreeBoundaryResult,
  MocMixedRegimePerimeterRequest,
  validate_mixed_regime_control_section,
  validate_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
)
from exhaust_plume.models.moc.mixed_regime_planar_free_boundary import (
  MocMixedRegimePlanarFreeBoundaryResult,
)
from exhaust_plume.models.moc.caustic_bridge import (
  MocCausticUpstreamBridge,
  sample_caustic_upstream_bridge,
)
from exhaust_plume.models.moc.caustic_remesh import (
  MocCausticShockRemeshRequest,
  MocCausticShockRemeshResult,
)
from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocCellClosureStatus,
  MocChainGeometryFidelity,
  MocChainTerminationReason,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.planner import (
  MocChainPlannerResult,
  MocFirstCellResearchChainPlannerResult,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.mixed_regime_entropy import (
  MocMixedRegimeEntropyHandoffResult,
  MocMixedRegimeEntropyInterfaceKind,
  MocMixedRegimeEntropyInterfaceSample,
)
from exhaust_plume.models.moc.mixed_regime_entropy_transport import (
  MocMixedRegimeEntropyTransportResult,
  MocMixedRegimeEntropyTransportStatus,
)
from exhaust_plume.models.moc.mixed_regime_variable_entropy import (
  MocMixedRegimeVariableEntropyFreeBoundaryResult,
  MocMixedRegimeVariableEntropyFreeBoundaryStatus,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  centerline_characteristic_point,
)
from exhaust_plume.models.moc.boundary import (
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
  MocPhysicalPostShockFieldStatus,
)
from exhaust_plume.models.moc.first_cell_candidate import (
  MocFirstCellCandidateResult,
)
from exhaust_plume.models.moc.first_cell_free_boundary import (
  MocFirstCellFreeBoundaryCorrectionResult,
  MocFirstCellFreeBoundaryCorrectionStatus,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
  MocReflectedDomainAlternatingSourceStatus,
  MocReflectedDomainAlternatingPhysicalFieldResult,
  MocReflectedDomainSolverOwnedFirstCellResult,
  MocReflectedDomainSolverOwnedFirstCellStatus,
  MocReflectedDomainGlobalShockRemeshResult,
  MocReflectedDomainGlobalShockRemeshStatus,
  MocReflectedDomainGlobalEulerShockBoundaryResult,
  MocReflectedDomainGlobalEulerShockBoundaryStatus,
  MocReflectedDomainOuterSourceResult,
  MocReflectedDomainOuterSourceStatus,
  MocReflectedDomainRemeshResult,
  MocReflectedDomainRemeshStatus,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockBoundaryState,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldStatus,
  MocShockBoundaryFitResult,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.shock_chain import MocTerminalShockCellFieldResult
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  assemble_source_characteristic_strip_with_source_pressures,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocReflectedTraceCompressionProfile,
  MocTerminalReflectionPatchResult,
  build_reflected_trace_compression_profile,
  classify_reflected_trace_polarity,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode
from exhaust_plume.models.moc.free_boundary import MocFreeBoundaryShockResult
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.util.aero.shock_validity import theta_beta_mach_residual

__all__ = (
  'MOC_CAUSTIC_REMESH_OPERATOR_ID',
  'MOC_CHAIN_PLANNER_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_REMESH_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_OUTER_SOURCE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_ALTERNATING_SOURCE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_SOLVER_OWNED_FIRST_CELL_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_SHOCK_REMESH_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_REFINEMENT_OPERATOR_ID',
  'MOC_MIXED_REGIME_FREE_BOUNDARY_OPERATOR_ID',
  'MOC_MIXED_REGIME_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_OPERATOR_ID',
  'MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MOC_MIXED_REGIME_CONTROL_SECTION_OPERATOR_ID',
  'MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID',
  'MOC_MIXED_REGIME_ENTROPY_HANDOFF_OPERATOR_ID',
  'MOC_MIXED_REGIME_ENTROPY_TRANSPORT_OPERATOR_ID',
  'MOC_MIXED_REGIME_VARIABLE_ENTROPY_FREE_BOUNDARY_OPERATOR_ID',
  'MOC_SHOCK_CELL_CHAIN_OPERATOR_ID',
  'MOC_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID',
  'MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID',
  'MOC_AMBIENT_CLOSED_PHYSICAL_FIELD_CHAIN_OPERATOR_ID',
  'MOC_TERMINAL_CLOSURE_OPERATOR_ID',
  'MOC_FIRST_CELL_CANDIDATE_OPERATOR_ID',
  'MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_OPERATOR_ID',
  'MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_REFINEMENT_OPERATOR_ID',
  'MOC_FIRST_CELL_RESEARCH_CHAIN_OPERATOR_ID',
  'MOC_FIRST_CELL_RESEARCH_CHAIN_REFINEMENT_OPERATOR_ID',
  'MocCausticRemeshMeasurement',
  'MocCausticRemeshMeasurementStatus',
  'MocCausticRemeshObservation',
  'MocChainPlannerMeasurement',
  'MocChainPlannerMeasurementStatus',
  'MocReflectedDomainRemeshMeasurement',
  'MocReflectedDomainRemeshMeasurementStatus',
  'MocReflectedDomainOuterSourceMeasurement',
  'MocReflectedDomainOuterSourceMeasurementStatus',
  'MocReflectedDomainAlternatingSourceMeasurement',
  'MocReflectedDomainAlternatingSourceMeasurementStatus',
  'MocReflectedDomainAlternatingPhysicalFieldMeasurement',
  'MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus',
  'MocReflectedDomainSolverOwnedFirstCellMeasurement',
  'MocReflectedDomainSolverOwnedFirstCellMeasurementStatus',
  'MocReflectedDomainGlobalShockRemeshMeasurement',
  'MocReflectedDomainGlobalShockRemeshMeasurementStatus',
  'MocReflectedDomainGlobalEulerShockBoundaryMeasurement',
  'MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus',
  'MocReflectedDomainAlternatingPhysicalFieldChainMeasurement',
  'MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus',
  'MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase',
  'MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement',
  'MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus',
  'MocMixedRegimePotentialMeasurement',
  'MocMixedRegimePotentialMeasurementStatus',
  'MocMixedRegimeFreeBoundaryMeasurement',
  'MocMixedRegimeFreeBoundaryMeasurementStatus',
  'MocMixedRegimeFreeBoundaryRefinementCase',
  'MocMixedRegimeFreeBoundaryRefinementMeasurement',
  'MocMixedRegimeFreeBoundaryRefinementMeasurementStatus',
  'MocMixedRegimePlanarFreeBoundaryMeasurement',
  'MocMixedRegimePlanarFreeBoundaryMeasurementStatus',
  'MocMixedRegimePlanarFreeBoundaryRefinementCase',
  'MocMixedRegimePlanarFreeBoundaryRefinementMeasurement',
  'MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus',
  'MocMixedRegimeControlSectionMeasurement',
  'MocMixedRegimeControlSectionMeasurementStatus',
  'MocMixedRegimeEntropyHandoffMeasurement',
  'MocMixedRegimeEntropyHandoffMeasurementStatus',
  'MocMixedRegimeEntropyTransportMeasurement',
  'MocMixedRegimeEntropyTransportMeasurementStatus',
  'MocMixedRegimeVariableEntropyFreeBoundaryMeasurement',
  'MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus',
  'MocTerminalClosureMeasurement',
  'MocTerminalClosureMeasurementStatus',
  'MocTerminalClosureObservation',
  'MocShockCellChainMeasurement',
  'MocShockCellChainRefinementCase',
  'MocShockCellChainRefinementMeasurement',
  'MocShockCellChainRefinementMeasurementStatus',
  'MocShockCellMeasurement',
  'MocShockCellMeasurementStatus',
  'MocShockCellObservation',
  'MocPhysicalFieldChainMeasurement',
  'MocPhysicalFieldChainMeasurementStatus',
  'MocFirstCellCandidateMeasurement',
  'MocFirstCellCandidateMeasurementStatus',
  'MocFirstCellFreeBoundaryCorrectionMeasurement',
  'MocFirstCellFreeBoundaryCorrectionMeasurementStatus',
  'MocFirstCellFreeBoundaryCorrectionRefinementMeasurement',
  'MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus',
  'MocFirstCellResearchChainMeasurement',
  'MocFirstCellResearchChainMeasurementStatus',
  'MocFirstCellResearchChainRefinementCase',
  'MocFirstCellResearchChainRefinementMeasurement',
  'MocFirstCellResearchChainRefinementMeasurementStatus',
  'measure_moc_caustic_remesh',
  'measure_moc_chain_planner',
  'measure_moc_reflected_domain_remesh',
  'measure_moc_reflected_domain_outer_source_curve',
  'measure_moc_reflected_domain_alternating_source',
  'measure_moc_reflected_domain_alternating_physical_field_chain',
  'measure_moc_reflected_domain_solver_owned_first_cell',
  'measure_moc_reflected_domain_global_shock_remesh',
  'measure_moc_reflected_domain_global_euler_shock_boundary',
  'measure_moc_reflected_domain_alternating_physical_field_chain_refinement',
  'measure_mixed_regime_compressible_potential_field',
  'measure_mixed_regime_free_boundary_reference',
  'measure_mixed_regime_free_boundary_refinement',
  'measure_mixed_regime_planar_free_boundary_reference',
  'measure_mixed_regime_planar_free_boundary_refinement',
  'measure_mixed_regime_control_section',
  'measure_mixed_regime_entropy_handoff',
  'measure_mixed_regime_entropy_transport_boundary',
  'measure_mixed_regime_variable_entropy_free_boundary',
  'measure_moc_terminal_closure',
  'measure_moc_shock_cell',
  'measure_moc_shock_cell_chain',
  'measure_moc_shock_cell_chain_refinement',
  'measure_moc_ambient_closed_physical_field_chain',
  'measure_first_cell_geometry_owned_candidate',
  'measure_first_cell_free_boundary_correction',
  'measure_first_cell_free_boundary_correction_refinement',
  'measure_first_cell_geometry_owned_research_chain',
  'measure_first_cell_geometry_owned_research_chain_refinement',
)


MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID = 'op.moc.shock-cell-geometry'
MOC_SHOCK_CELL_CHAIN_OPERATOR_ID = 'op.moc.shock-cell-chain'
MOC_AMBIENT_CLOSED_PHYSICAL_FIELD_CHAIN_OPERATOR_ID = (
  'op.moc.ambient-closed-physical-field-chain'
)
MOC_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.shock-cell-chain-refinement'
)
MOC_TERMINAL_CLOSURE_OPERATOR_ID = 'op.moc.terminal-closure'
MOC_FIRST_CELL_CANDIDATE_OPERATOR_ID = (
  'op.moc.first-cell-geometry-owned-candidate'
)
MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_OPERATOR_ID = (
  'op.moc.first-cell-free-boundary-correction'
)
MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_REFINEMENT_OPERATOR_ID = (
  'op.moc.first-cell-free-boundary-correction-refinement'
)
MOC_FIRST_CELL_RESEARCH_CHAIN_OPERATOR_ID = (
  'op.moc.first-cell-geometry-owned-research-chain'
)
MOC_FIRST_CELL_RESEARCH_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.first-cell-geometry-owned-research-chain-refinement'
)
MOC_CAUSTIC_REMESH_OPERATOR_ID = 'op.moc.caustic-remesh'
MOC_CHAIN_PLANNER_OPERATOR_ID = 'op.moc.chain-planner'
MOC_REFLECTED_DOMAIN_REMESH_OPERATOR_ID = 'op.moc.reflected-domain-remesh'
MOC_REFLECTED_DOMAIN_OUTER_SOURCE_OPERATOR_ID = (
  'op.moc.reflected-domain-outer-source'
)
MOC_REFLECTED_DOMAIN_ALTERNATING_SOURCE_OPERATOR_ID = (
  'op.moc.reflected-domain-alternating-source'
)
MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_OPERATOR_ID = (
  'op.moc.reflected-domain-alternating-physical-field'
)
MOC_REFLECTED_DOMAIN_SOLVER_OWNED_FIRST_CELL_OPERATOR_ID = (
  'op.moc.reflected-domain-solver-owned-first-cell'
)
MOC_REFLECTED_DOMAIN_GLOBAL_SHOCK_REMESH_OPERATOR_ID = (
  'op.moc.reflected-domain-global-shock-remesh'
)
MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_OPERATOR_ID = (
  'op.moc.reflected-domain-global-euler-shock-boundary'
)
MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_OPERATOR_ID = (
  'op.moc.reflected-domain-alternating-physical-field-chain'
)
MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain-alternating-physical-field-chain-refinement'
)
MOC_MIXED_REGIME_FREE_BOUNDARY_OPERATOR_ID = (
  'op.moc.mixed-regime-free-boundary-reference'
)
MOC_MIXED_REGIME_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.mixed-regime-free-boundary-refinement'
)
MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_OPERATOR_ID = (
  'op.moc.mixed-regime-planar-free-boundary-reference'
)
MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.mixed-regime-planar-free-boundary-refinement'
)
MOC_MIXED_REGIME_CONTROL_SECTION_OPERATOR_ID = (
  'op.moc.mixed-regime-control-section'
)
MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID = 'op.moc.mixed-regime-compressible-potential'
MOC_MIXED_REGIME_ENTROPY_HANDOFF_OPERATOR_ID = (
  'op.moc.mixed-regime-entropy-handoff'
)
MOC_MIXED_REGIME_ENTROPY_TRANSPORT_OPERATOR_ID = (
  'op.moc.mixed-regime-entropy-transport-boundary'
)
MOC_MIXED_REGIME_VARIABLE_ENTROPY_FREE_BOUNDARY_OPERATOR_ID = (
  'op.moc.mixed-regime-variable-entropy-free-boundary'
)

Point = tuple[float, float]


class MocMixedRegimeEntropyHandoffMeasurementStatus(str, Enum):
  """Outcome of independently measuring the reflected entropy handoff."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'entropy-handoff-request-failure'
  HANDOFF_FAILURE = 'entropy-handoff-result-failure'
  SAMPLE_FAILURE = 'entropy-handoff-sample-failure'
  GEOMETRY_FAILURE = 'entropy-handoff-geometry-failure'
  PRESSURE_FAILURE = 'entropy-handoff-pressure-failure'
  CONSISTENCY_FAILURE = 'entropy-handoff-consistency-failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeEntropyHandoffMeasurement:
  """Independent evidence for a pressure-loss-aware terminal interface.

  The operator reconstructs expected interface samples from the request and
  compares them with the returned handoff.  It does not use the handoff's
  convenience flags or recompute the handoff by calling its builder.
  """

  status: MocMixedRegimeEntropyHandoffMeasurementStatus
  operator_id: str = MOC_MIXED_REGIME_ENTROPY_HANDOFF_OPERATOR_ID
  handoff: MocMixedRegimeEntropyHandoffResult | None = None
  request_verified: bool = False
  sample_count: int = 0
  expected_sample_count: int = 0
  terminal_sample_index: int | None = None
  interface_geometry_verified: bool = False
  terminal_seam_verified: bool = False
  shock_loss_verified: bool = False
  entropy_profile_verified: bool = False
  handoff_metrics_verified: bool = False
  maximum_interface_point_residual_m: float | None = None
  maximum_cumulative_arc_length_residual_m: float | None = None
  minimum_total_pressure_ratio: float | None = None
  maximum_entropy_production_nondimensional: float | None = None
  maximum_total_pressure_gain_Pa: float | None = None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocMixedRegimeEntropyHandoffMeasurementStatus,
    ):
      raise TypeError(
        'status must be a MocMixedRegimeEntropyHandoffMeasurementStatus'
      )
    if self.handoff is not None and not isinstance(
      self.handoff,
      MocMixedRegimeEntropyHandoffResult,
    ):
      raise TypeError(
        'handoff must be a MocMixedRegimeEntropyHandoffResult or None'
      )
    for name in (
      'sample_count',
      'expected_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.terminal_sample_index is not None:
      if (
        isinstance(self.terminal_sample_index, bool)
        or not isinstance(self.terminal_sample_index, int)
        or self.terminal_sample_index < 0
      ):
        raise ValueError(
          'terminal_sample_index must be a nonnegative integer when supplied'
        )
    for name in (
      'maximum_interface_point_residual_m',
      'maximum_cumulative_arc_length_residual_m',
      'minimum_total_pressure_ratio',
      'maximum_entropy_production_nondimensional',
      'maximum_total_pressure_gain_Pa',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    for name in (
      'request_verified',
      'interface_geometry_verified',
      'terminal_seam_verified',
      'shock_loss_verified',
      'entropy_profile_verified',
      'handoff_metrics_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeEntropyHandoffMeasurementStatus.CONVERGED
  ####

  @property
  def handoff_verified(self) -> bool:
    return bool(
      self.converged
      and self.request_verified
      and self.interface_geometry_verified
      and self.terminal_seam_verified
      and self.shock_loss_verified
      and self.entropy_profile_verified
      and self.handoff_metrics_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'handoff_verified': self.handoff_verified,
      'request_verified': self.request_verified,
      'sample_count': self.sample_count,
      'expected_sample_count': self.expected_sample_count,
      'terminal_sample_index': self.terminal_sample_index,
      'interface_geometry_verified': self.interface_geometry_verified,
      'terminal_seam_verified': self.terminal_seam_verified,
      'shock_loss_verified': self.shock_loss_verified,
      'entropy_profile_verified': self.entropy_profile_verified,
      'handoff_metrics_verified': self.handoff_metrics_verified,
      'maximum_interface_point_residual_m': self.maximum_interface_point_residual_m,
      'maximum_cumulative_arc_length_residual_m': (
        self.maximum_cumulative_arc_length_residual_m
      ),
      'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
      'maximum_entropy_production_nondimensional': (
        self.maximum_entropy_production_nondimensional
      ),
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####


def _entropy_handoff_measurement_failure(
  status: MocMixedRegimeEntropyHandoffMeasurementStatus,
  *,
  handoff: MocMixedRegimeEntropyHandoffResult | None = None,
  request_verified: bool = False,
  sample_count: int = 0,
  expected_sample_count: int = 0,
  terminal_sample_index: int | None = None,
  interface_geometry_verified: bool = False,
  terminal_seam_verified: bool = False,
  shock_loss_verified: bool = False,
  entropy_profile_verified: bool = False,
  handoff_metrics_verified: bool = False,
  maximum_interface_point_residual_m: float | None = None,
  maximum_cumulative_arc_length_residual_m: float | None = None,
  minimum_total_pressure_ratio: float | None = None,
  maximum_entropy_production_nondimensional: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  message: str,
) -> MocMixedRegimeEntropyHandoffMeasurement:
  return MocMixedRegimeEntropyHandoffMeasurement(
    status=status,
    handoff=handoff,
    request_verified=request_verified,
    sample_count=sample_count,
    expected_sample_count=expected_sample_count,
    terminal_sample_index=terminal_sample_index,
    interface_geometry_verified=interface_geometry_verified,
    terminal_seam_verified=terminal_seam_verified,
    shock_loss_verified=shock_loss_verified,
    entropy_profile_verified=entropy_profile_verified,
    handoff_metrics_verified=handoff_metrics_verified,
    maximum_interface_point_residual_m=maximum_interface_point_residual_m,
    maximum_cumulative_arc_length_residual_m=(
      maximum_cumulative_arc_length_residual_m
    ),
    minimum_total_pressure_ratio=minimum_total_pressure_ratio,
    maximum_entropy_production_nondimensional=(
      maximum_entropy_production_nondimensional
    ),
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def _entropy_close(first: float, second: float, tolerance: float) -> bool:
  return abs(float(first) - float(second)) <= tolerance * max(
    1.0,
    abs(float(first)),
    abs(float(second)),
  )


def measure_mixed_regime_entropy_handoff(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeEntropyHandoffMeasurement:
  """Independently remeasure a reflected shock-interface entropy handoff."""

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if not isinstance(handoff, MocMixedRegimeEntropyHandoffResult):
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.INVALID_INPUT,
      message='handoff must be a MocMixedRegimeEntropyHandoffResult',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if handoff.request != request:
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.REQUEST_FAILURE,
      handoff=handoff,
      message='entropy handoff did not retain the exact perimeter request',
    )
  if handoff.status.value != 'converged-reflected-downstream-entropy-handoff':
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.HANDOFF_FAILURE,
      handoff=handoff,
      message=f'entropy handoff is not converged: {handoff.message}',
    )

  terminal = request.terminal
  terminal_values = (
    terminal.shock_point_m,
    terminal.downstream_mach,
    terminal.downstream_flow_angle_rad,
    terminal.upstream_total_pressure_Pa,
    terminal.downstream_total_pressure_Pa,
    terminal.upstream_state,
  )
  if any(value is None for value in terminal_values):
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.REQUEST_FAILURE,
      handoff=handoff,
      message='request terminal does not expose complete entropy data',
    )
  (
    terminal_point,
    terminal_mach,
    terminal_angle,
    terminal_upstream_pressure,
    terminal_downstream_pressure,
    terminal_upstream_state,
  ) = terminal_values
  assert terminal_point is not None
  assert terminal_mach is not None
  assert terminal_angle is not None
  assert terminal_upstream_pressure is not None
  assert terminal_downstream_pressure is not None
  assert terminal_upstream_state is not None

  expected: list[MocMixedRegimeEntropyInterfaceSample] = []
  for index, patch_sample in enumerate(request.supersonic_patch):
    if not isinstance(patch_sample, MocPostShockBoundaryState):
      return _entropy_handoff_measurement_failure(
        MocMixedRegimeEntropyHandoffMeasurementStatus.REQUEST_FAILURE,
        handoff=handoff,
        message=f'request patch sample {index} has an invalid type',
      )
    try:
      expected.append(MocMixedRegimeEntropyInterfaceSample(
        point_m=patch_sample.point_m,
        downstream_mach=patch_sample.state.mach,
        downstream_flow_angle_rad=patch_sample.state.theta_rad,
        gamma=patch_sample.state.gamma,
        upstream_total_pressure_Pa=patch_sample.upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=patch_sample.downstream_total_pressure_Pa,
        interface_kind=MocMixedRegimeEntropyInterfaceKind.OBLIQUE_SHOCK,
      ))
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _entropy_handoff_measurement_failure(
        MocMixedRegimeEntropyHandoffMeasurementStatus.REQUEST_FAILURE,
        handoff=handoff,
        message=f'request patch sample {index} could not be measured: {error}',
      )
  try:
    expected.append(MocMixedRegimeEntropyInterfaceSample(
      point_m=terminal_point,
      downstream_mach=terminal_mach,
      downstream_flow_angle_rad=terminal_angle,
      gamma=terminal_upstream_state.gamma,
      upstream_total_pressure_Pa=terminal_upstream_pressure,
      downstream_total_pressure_Pa=terminal_downstream_pressure,
      interface_kind=MocMixedRegimeEntropyInterfaceKind.NORMAL_SHOCK_TERMINAL,
    ))
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.REQUEST_FAILURE,
      handoff=handoff,
      message=f'request terminal could not be measured: {error}',
    )

  expected_tuple = tuple(expected)
  measured_tuple = handoff.samples
  common = {
    'handoff': handoff,
    'request_verified': True,
    'sample_count': len(measured_tuple),
    'expected_sample_count': len(expected_tuple),
    'terminal_sample_index': handoff.terminal_sample_index,
  }
  if len(measured_tuple) != len(expected_tuple):
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.SAMPLE_FAILURE,
      message=(
        'entropy handoff sample count does not match the exact patch plus '
        f'terminal count: measured={len(measured_tuple)}, '
        f'expected={len(expected_tuple)}'
      ),
      **common,
    )
  if handoff.terminal_sample_index != len(expected_tuple) - 1:
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.CONSISTENCY_FAILURE,
      message='entropy handoff terminal index is not the final interface sample',
      **common,
    )
  maximum_point_residual = max(
    hypot(measured.point_m[0] - expected.point_m[0], measured.point_m[1] - expected.point_m[1])
    for measured, expected in zip(measured_tuple, expected_tuple, strict=True)
  )
  scalar_fields = (
    'downstream_mach',
    'downstream_flow_angle_rad',
    'gamma',
    'upstream_total_pressure_Pa',
    'downstream_total_pressure_Pa',
  )
  scalar_consistent = all(
    _entropy_close(
      getattr(measured, field_name),
      getattr(expected, field_name),
      pressure_tolerance if 'pressure' in field_name else position_tolerance_m,
    )
    for measured, expected in zip(measured_tuple, expected_tuple, strict=True)
    for field_name in scalar_fields
  )
  kind_consistent = all(
    measured.interface_kind is expected.interface_kind
    for measured, expected in zip(measured_tuple, expected_tuple, strict=True)
  )
  sample_consistent = (
    maximum_point_residual <= position_tolerance_m
    and scalar_consistent
    and kind_consistent
  )
  if not sample_consistent:
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.SAMPLE_FAILURE,
      maximum_interface_point_residual_m=maximum_point_residual,
      message='entropy handoff samples do not reproduce the request source data',
      **common,
    )

  points = tuple(sample.point_m for sample in measured_tuple)
  segment_lengths = tuple(
    hypot(second[0] - first[0], second[1] - first[1])
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  geometry_verified = bool(
    len(handoff.interface_points_m) == len(points)
    and all(
      hypot(measured[0] - expected[0], measured[1] - expected[1])
      <= position_tolerance_m
      for measured, expected in zip(
        handoff.interface_points_m,
        points,
        strict=True,
      )
    )
    and all(length > position_tolerance_m for length in segment_lengths)
  )
  expected_arc = [0.0]
  for length in segment_lengths:
    expected_arc.append(expected_arc[-1] + length)
  maximum_arc_residual: float | None = (
    max(
      abs(measured - expected)
      for measured, expected in zip(
        handoff.cumulative_arc_length_m,
        expected_arc,
        strict=True,
      )
    )
    if len(handoff.cumulative_arc_length_m) == len(expected_arc)
    else None
  )
  geometry_verified = bool(
    geometry_verified
    and maximum_arc_residual is not None
    and maximum_arc_residual <= position_tolerance_m
  )
  if not geometry_verified:
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.GEOMETRY_FAILURE,
      interface_geometry_verified=False,
      maximum_interface_point_residual_m=maximum_point_residual,
      maximum_cumulative_arc_length_residual_m=maximum_arc_residual,
      message='entropy handoff interface path or cumulative arc length failed independent geometry checks',
      **common,
    )

  pressure_gain = max(
    max(
      0.0,
      sample.downstream_total_pressure_Pa
      - sample.upstream_total_pressure_Pa,
    )
    for sample in measured_tuple
  )
  pressure_loss_verified = all(
    sample.downstream_total_pressure_Pa
    < sample.upstream_total_pressure_Pa
    for sample in measured_tuple
  )
  entropy_values = tuple(
    log(sample.upstream_total_pressure_Pa / sample.downstream_total_pressure_Pa)
    for sample in measured_tuple
  )
  entropy_profile_verified = all(
    isfinite(value) and value > 0.0 for value in entropy_values
  )
  minimum_ratio = min(sample.total_pressure_ratio for sample in measured_tuple)
  maximum_entropy = max(entropy_values)
  terminal = measured_tuple[-1]
  terminal_seam_verified = bool(
    terminal.interface_kind is MocMixedRegimeEntropyInterfaceKind.NORMAL_SHOCK_TERMINAL
    and terminal.point_m == terminal_point
    and _entropy_close(terminal.downstream_mach, terminal_mach, position_tolerance_m)
    and _entropy_close(terminal.downstream_flow_angle_rad, terminal_angle, position_tolerance_m)
    and _entropy_close(
      terminal.upstream_total_pressure_Pa,
      terminal_upstream_pressure,
      pressure_tolerance,
    )
    and _entropy_close(
      terminal.downstream_total_pressure_Pa,
      terminal_downstream_pressure,
      pressure_tolerance,
    )
  )
  reported_metrics = (
    handoff.interface_geometry_verified
    and handoff.terminal_seam_verified
    and handoff.shock_loss_verified
    and handoff.entropy_transport_verified
    and handoff.maximum_interface_segment_length_m is not None
    and handoff.minimum_total_pressure_ratio is not None
    and handoff.maximum_entropy_production_nondimensional is not None
    and handoff.maximum_total_pressure_gain_Pa is not None
  )
  handoff_metrics_verified = bool(
    reported_metrics
    and _entropy_close(
      handoff.maximum_interface_segment_length_m,
      max(segment_lengths),
      position_tolerance_m,
    )
    and _entropy_close(
      handoff.minimum_total_pressure_ratio,
      minimum_ratio,
      pressure_tolerance,
    )
    and _entropy_close(
      handoff.maximum_entropy_production_nondimensional,
      maximum_entropy,
      pressure_tolerance,
    )
    and _entropy_close(
      handoff.maximum_total_pressure_gain_Pa,
      pressure_gain,
      pressure_tolerance,
    )
  )
  if not (
    terminal_seam_verified
    and pressure_loss_verified
    and entropy_profile_verified
    and handoff_metrics_verified
  ):
    return _entropy_handoff_measurement_failure(
      MocMixedRegimeEntropyHandoffMeasurementStatus.PRESSURE_FAILURE,
      interface_geometry_verified=True,
      terminal_seam_verified=terminal_seam_verified,
      shock_loss_verified=pressure_loss_verified,
      entropy_profile_verified=entropy_profile_verified,
      handoff_metrics_verified=handoff_metrics_verified,
      maximum_interface_point_residual_m=maximum_point_residual,
      maximum_cumulative_arc_length_residual_m=maximum_arc_residual,
      minimum_total_pressure_ratio=minimum_ratio,
      maximum_entropy_production_nondimensional=maximum_entropy,
      maximum_total_pressure_gain_Pa=pressure_gain,
      message='entropy handoff pressure-loss or terminal-seam checks failed',
      **common,
    )
  return MocMixedRegimeEntropyHandoffMeasurement(
    status=MocMixedRegimeEntropyHandoffMeasurementStatus.CONVERGED,
    handoff=handoff,
    request_verified=True,
    sample_count=len(measured_tuple),
    expected_sample_count=len(expected_tuple),
    terminal_sample_index=handoff.terminal_sample_index,
    interface_geometry_verified=True,
    terminal_seam_verified=True,
    shock_loss_verified=True,
    entropy_profile_verified=True,
    handoff_metrics_verified=True,
    maximum_interface_point_residual_m=maximum_point_residual,
    maximum_cumulative_arc_length_residual_m=maximum_arc_residual,
    minimum_total_pressure_ratio=minimum_ratio,
    maximum_entropy_production_nondimensional=maximum_entropy,
    maximum_total_pressure_gain_Pa=pressure_gain,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent entropy-interface measurement reproduced the exact shock '
      'patch and terminal, arc-length ordering, strict total-pressure loss, '
      'and entropy coordinate; downstream entropy transport and free-boundary '
      'closure remain pending'
    ),
  )
####


class MocFirstCellCandidateMeasurementStatus(str, Enum):
  """Outcome for independent first-cell candidate measurements."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_measurement_failure'
  AMBIENT_FAILURE = 'ambient_measurement_failure'
  FIELD_FAILURE = 'field_measurement_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellCandidateMeasurement:
  """Raw-data measurement of a geometry-owned first-cell candidate."""

  status: MocFirstCellCandidateMeasurementStatus
  candidate_status: str
  sample_count: int
  shock_fit_verified: bool
  shock_rankine_hugoniot_verified: bool
  shock_pressure_loss_verified: bool
  attachment_pressure_verified: bool
  ambient_boundary_verified: bool
  field_topology_verified: bool
  field_physical_closure_verified: bool
  field_state_sampling_verified: bool
  upstream_shock_coupling_verified: bool
  maximum_rankine_hugoniot_residual: float | None
  maximum_shock_geometry_residual_rad: float | None
  attachment_pressure_residual: float | None
  maximum_ambient_pressure_residual: float | None
  maximum_ambient_tangent_residual: float | None
  centerline_flow_angle_residual_rad: float | None
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  external_validation_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocFirstCellCandidateMeasurementStatus.CONVERGED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.converged and self.field_physical_closure_verified
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_FIRST_CELL_CANDIDATE_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'candidate_status': self.candidate_status,
      'sample_count': self.sample_count,
      'shock_fit_verified': self.shock_fit_verified,
      'shock_rankine_hugoniot_verified': self.shock_rankine_hugoniot_verified,
      'shock_pressure_loss_verified': self.shock_pressure_loss_verified,
      'attachment_pressure_verified': self.attachment_pressure_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'field_topology_verified': self.field_topology_verified,
      'field_physical_closure_verified': self.field_physical_closure_verified,
      'field_state_sampling_verified': self.field_state_sampling_verified,
      'upstream_shock_coupling_verified': self.upstream_shock_coupling_verified,
      'maximum_rankine_hugoniot_residual': self.maximum_rankine_hugoniot_residual,
      'maximum_shock_geometry_residual_rad': self.maximum_shock_geometry_residual_rad,
      'attachment_pressure_residual': self.attachment_pressure_residual,
      'maximum_ambient_pressure_residual': self.maximum_ambient_pressure_residual,
      'maximum_ambient_tangent_residual': self.maximum_ambient_tangent_residual,
      'centerline_flow_angle_residual_rad': self.centerline_flow_angle_residual_rad,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####


def _candidate_shock_tangent(
  points: Sequence[tuple[float, float]],
  index: int,
) -> float:
  if index == 0:
    first, second = points[0], points[1]
  elif index == len(points) - 1:
    first, second = points[-2], points[-1]
  else:
    first, second = points[index - 1], points[index + 1]
  return atan2(second[1] - first[1], second[0] - first[0])
####


def _first_cell_candidate_measurement_failure(
  status: MocFirstCellCandidateMeasurementStatus,
  *,
  candidate_status: str,
  sample_count: int = 0,
  shock_fit_verified: bool = False,
  shock_rankine_hugoniot_verified: bool = False,
  shock_pressure_loss_verified: bool = False,
  attachment_pressure_verified: bool = False,
  ambient_boundary_verified: bool = False,
  field_topology_verified: bool = False,
  field_physical_closure_verified: bool = False,
  field_state_sampling_verified: bool = False,
  upstream_shock_coupling_verified: bool = False,
  maximum_rankine_hugoniot_residual: float | None = None,
  maximum_shock_geometry_residual_rad: float | None = None,
  attachment_pressure_residual: float | None = None,
  maximum_ambient_pressure_residual: float | None = None,
  maximum_ambient_tangent_residual: float | None = None,
  centerline_flow_angle_residual_rad: float | None = None,
  canonical_free_boundary_verified: bool = False,
  canonical_euler_verified: bool = False,
  external_validation_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  message: str,
) -> MocFirstCellCandidateMeasurement:
  return MocFirstCellCandidateMeasurement(
    status=status,
    candidate_status=candidate_status,
    sample_count=sample_count,
    shock_fit_verified=shock_fit_verified,
    shock_rankine_hugoniot_verified=shock_rankine_hugoniot_verified,
    shock_pressure_loss_verified=shock_pressure_loss_verified,
    attachment_pressure_verified=attachment_pressure_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    field_topology_verified=field_topology_verified,
    field_physical_closure_verified=field_physical_closure_verified,
    field_state_sampling_verified=field_state_sampling_verified,
    upstream_shock_coupling_verified=upstream_shock_coupling_verified,
    maximum_rankine_hugoniot_residual=maximum_rankine_hugoniot_residual,
    maximum_shock_geometry_residual_rad=maximum_shock_geometry_residual_rad,
    attachment_pressure_residual=attachment_pressure_residual,
    maximum_ambient_pressure_residual=maximum_ambient_pressure_residual,
    maximum_ambient_tangent_residual=maximum_ambient_tangent_residual,
    centerline_flow_angle_residual_rad=centerline_flow_angle_residual_rad,
    canonical_free_boundary_verified=canonical_free_boundary_verified,
    canonical_euler_verified=canonical_euler_verified,
    external_validation_verified=external_validation_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    message=message,
  )
####


def measure_first_cell_geometry_owned_candidate(
  candidate: MocFirstCellCandidateResult,
  *,
  shock_residual_tolerance_rad: float = 1.0e-8,
  pressure_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-8,
) -> MocFirstCellCandidateMeasurement:
  """Independently remeasure the candidate's shock, boundary, and field.

  This operator consumes the retained typed data only.  It recomputes local
  theta-beta-Mach residuals, shock pressure-loss ratios, ambient pressure and
  tangent residuals, and the immutable physical-field gate; it never calls
  the candidate solver.
  """

  if not isinstance(candidate, MocFirstCellCandidateResult):
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.INVALID_INPUT,
      candidate_status='invalid-input',
      message='candidate must be a MocFirstCellCandidateResult',
    )
  try:
    shock_tolerance = float(shock_residual_tolerance_rad)
    pressure_tolerance = float(pressure_residual_tolerance)
    position_tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.INVALID_INPUT,
      candidate_status=candidate.status.value,
      message='measurement tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (shock_tolerance, pressure_tolerance, position_tolerance)
  ):
    raise ValueError('measurement tolerances must be finite and positive')
  points = tuple(candidate.shock_points_m)
  fit = candidate.shock_fit
  if (
    fit is None
    or not fit.converged
    or len(points) < 3
    or len(fit.boundary_states) != len(points)
    or len(fit.upstream_states) != len(points)
    or len(fit.upstream_total_pressure_Pa) != len(points)
  ):
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.SHOCK_FAILURE,
      candidate_status=candidate.status.value,
      sample_count=len(points),
      message='candidate does not retain a complete converged shock fit',
    )
  shock_geometry_verified = True
  rh_residuals: list[float] = []
  shock_loss_verified = True
  for index, (point, sample, upstream, upstream_pressure) in enumerate(zip(
    points,
    fit.boundary_states,
    fit.upstream_states,
    fit.upstream_total_pressure_Pa,
    strict=True,
  )):
    shock_geometry_verified = shock_geometry_verified and (
      abs(point[0] - sample.point_m[0]) <= position_tolerance
      and abs(point[1] - sample.point_m[1]) <= position_tolerance
      and abs(upstream.x_m - point[0]) <= position_tolerance
      and abs(upstream.y_m - point[1]) <= position_tolerance
      and isfinite(float(upstream_pressure))
      and float(upstream_pressure) > 0.0
    )
    tangent = _candidate_shock_tangent(points, index)
    beta = upstream.theta_rad - tangent
    turn = sample.state.theta_rad - upstream.theta_rad
    try:
      residual = abs(theta_beta_mach_residual(
        theta_rad=turn,
        beta_rad=beta,
        mach=upstream.mach,
        gamma=upstream.gamma,
      ))
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      residual = float('inf')
    rh_residuals.append(float(residual))
    ratio = (
      sample.downstream_total_pressure_Pa
      / sample.upstream_total_pressure_Pa
    )
    zero_start_allowed = bool(
      index == 0
      and candidate.field is not None
      and candidate.field.zero_strength_shock_start_allowed
    )
    zero_end_allowed = bool(
      index == len(points) - 1
      and candidate.field is not None
      and candidate.field.zero_strength_shock_endpoints_allowed
    )
    shock_loss_verified = shock_loss_verified and (
      0.0 < ratio < 1.0
      or (
        abs(ratio - 1.0) <= pressure_tolerance
        and (zero_start_allowed or zero_end_allowed)
      )
    )
  maximum_rh = max(rh_residuals, default=None)
  shock_fit_verified = shock_geometry_verified and (
    maximum_rh is not None and maximum_rh <= shock_tolerance
  )
  if not shock_fit_verified:
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.SHOCK_FAILURE,
      candidate_status=candidate.status.value,
      sample_count=len(points),
      shock_fit_verified=shock_geometry_verified,
      shock_rankine_hugoniot_verified=(
        maximum_rh is not None and maximum_rh <= shock_tolerance
      ),
      shock_pressure_loss_verified=shock_loss_verified,
      maximum_rankine_hugoniot_residual=maximum_rh,
      maximum_shock_geometry_residual_rad=max(
        (abs(value) for value in fit.shock_angle_residuals_rad),
        default=None,
      ),
      chain_promotion_blocked=candidate.chain_promotion_blocked,
      production_claim_allowed=candidate.production_claim_allowed,
      message='independent shock tangent/RH residual exceeded tolerance',
    )
  march = candidate.ambient_march
  if march is None or not march.converged:
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.AMBIENT_FAILURE,
      candidate_status=candidate.status.value,
      sample_count=len(points),
      shock_fit_verified=True,
      shock_rankine_hugoniot_verified=True,
      shock_pressure_loss_verified=shock_loss_verified,
      maximum_rankine_hugoniot_residual=maximum_rh,
      maximum_shock_geometry_residual_rad=max(
        (abs(value) for value in fit.shock_angle_residuals_rad),
        default=None,
      ),
      chain_promotion_blocked=candidate.chain_promotion_blocked,
      production_claim_allowed=candidate.production_claim_allowed,
      message='candidate does not retain a converged ambient boundary march',
    )
  ambient = validate_ambient_pressure_boundary(
    march.boundary_samples,
    float(march.ambient_boundary.ambient_pressure_Pa),
    position_tolerance_m=position_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=pressure_tolerance,
  )
  attachment_residual = None
  ambient_pressure = ambient.ambient_pressure_Pa
  if ambient_pressure is not None:
    first = fit.boundary_states[0]
    first_static = first.downstream_total_pressure_Pa / (
      1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach * first.state.mach
    ) ** (first.state.gamma / (first.state.gamma - 1.0))
    attachment_residual = (first_static - ambient_pressure) / ambient_pressure
  attachment_verified = (
    attachment_residual is not None
    and abs(attachment_residual) <= pressure_tolerance
  )
  ambient_verified = ambient.converged
  if not ambient_verified or not attachment_verified or not shock_loss_verified:
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.AMBIENT_FAILURE,
      candidate_status=candidate.status.value,
      sample_count=len(points),
      shock_fit_verified=True,
      shock_rankine_hugoniot_verified=True,
      shock_pressure_loss_verified=shock_loss_verified,
      attachment_pressure_verified=attachment_verified,
      ambient_boundary_verified=ambient_verified,
      maximum_rankine_hugoniot_residual=maximum_rh,
      maximum_shock_geometry_residual_rad=max(
        (abs(value) for value in fit.shock_angle_residuals_rad),
        default=None,
      ),
      attachment_pressure_residual=attachment_residual,
      maximum_ambient_pressure_residual=ambient.maximum_absolute_pressure_residual,
      maximum_ambient_tangent_residual=ambient.maximum_absolute_tangent_residual,
      centerline_flow_angle_residual_rad=candidate.centerline_flow_angle_residual_rad,
      chain_promotion_blocked=candidate.chain_promotion_blocked,
      production_claim_allowed=candidate.production_claim_allowed,
      message='independent ambient pressure, tangent, or shock-loss gate failed',
    )
  field = candidate.field
  if field is None:
    return _first_cell_candidate_measurement_failure(
      MocFirstCellCandidateMeasurementStatus.FIELD_FAILURE,
      candidate_status=candidate.status.value,
      sample_count=len(points),
      shock_fit_verified=True,
      shock_rankine_hugoniot_verified=True,
      shock_pressure_loss_verified=True,
      attachment_pressure_verified=True,
      ambient_boundary_verified=True,
      maximum_rankine_hugoniot_residual=maximum_rh,
      maximum_shock_geometry_residual_rad=max(
        (abs(value) for value in fit.shock_angle_residuals_rad),
        default=None,
      ),
      attachment_pressure_residual=attachment_residual,
      maximum_ambient_pressure_residual=ambient.maximum_absolute_pressure_residual,
      maximum_ambient_tangent_residual=ambient.maximum_absolute_tangent_residual,
      centerline_flow_angle_residual_rad=candidate.centerline_flow_angle_residual_rad,
      chain_promotion_blocked=candidate.chain_promotion_blocked,
      production_claim_allowed=candidate.production_claim_allowed,
      message='candidate does not retain a physical characteristic field',
    )
  field_gates = field.physical_closure_gates
  topology_verified = bool(
    field_gates.get('topology_verified', False)
    and field_gates.get('physical_boundary_paths_verified', False)
  )
  field_physical = all(field_gates.values())
  state_sampling = field.state_sampling_available
  upstream_coupling = field.upstream_shock_coupling_verified
  converged = bool(
    candidate.converged
    and shock_fit_verified
    and shock_loss_verified
    and attachment_verified
    and ambient_verified
    and topology_verified
    and field_physical
    and state_sampling
    and upstream_coupling
    and candidate.chain_promotion_blocked
    and not candidate.production_claim_allowed
  )
  status = (
    MocFirstCellCandidateMeasurementStatus.CONVERGED
    if converged
    else MocFirstCellCandidateMeasurementStatus.FIELD_FAILURE
  )
  return _first_cell_candidate_measurement_failure(
    status,
    candidate_status=candidate.status.value,
    sample_count=len(points),
    shock_fit_verified=shock_fit_verified,
    shock_rankine_hugoniot_verified=True,
    shock_pressure_loss_verified=shock_loss_verified,
    attachment_pressure_verified=attachment_verified,
    ambient_boundary_verified=ambient_verified,
    field_topology_verified=topology_verified,
    field_physical_closure_verified=field_physical,
    field_state_sampling_verified=state_sampling,
    upstream_shock_coupling_verified=upstream_coupling,
    maximum_rankine_hugoniot_residual=maximum_rh,
    maximum_shock_geometry_residual_rad=max(
      (abs(value) for value in fit.shock_angle_residuals_rad),
      default=None,
    ),
    attachment_pressure_residual=attachment_residual,
    maximum_ambient_pressure_residual=ambient.maximum_absolute_pressure_residual,
    maximum_ambient_tangent_residual=ambient.maximum_absolute_tangent_residual,
    centerline_flow_angle_residual_rad=candidate.centerline_flow_angle_residual_rad,
    canonical_free_boundary_verified=candidate.canonical_free_boundary_verified,
    canonical_euler_verified=candidate.canonical_euler_verified,
    external_validation_verified=candidate.external_validation_verified,
    chain_promotion_blocked=candidate.chain_promotion_blocked,
    production_claim_allowed=candidate.production_claim_allowed,
    message=(
      'independent geometry/RH, ambient-boundary, topology, state-sampling, '
      'and upstream-coupling measurement passed; canonical reflected '
      'free-boundary, Euler, and external-validation gates remain pending'
      if converged
      else 'independent physical-field evidence did not pass every gate'
    ),
  )
####


class MocFirstCellFreeBoundaryCorrectionMeasurementStatus(str, Enum):
  """Outcome of independently measuring a first-cell shape correction."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'correction_geometry_measurement_failure'
  TRIAL_FAILURE = 'correction_trial_measurement_failure'
  RESIDUAL_FAILURE = 'correction_residual_measurement_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellFreeBoundaryCorrectionMeasurement:
  """Independent audit of the bounded axial-shape correction.

  ``CONVERGED`` means that the returned correction outcome and all retained
  trial data are internally consistent.  It does not mean that a
  ``NO_BRACKET`` outcome found a physical root.  The canonical reflected
  free-boundary, Euler, external-validation, and product gates remain false.
  """

  status: MocFirstCellFreeBoundaryCorrectionMeasurementStatus
  correction_status: str
  sample_count: int
  trial_count: int
  shape_parameter_name: str
  shape_family_verified: bool
  trial_residuals_verified: bool
  selected_trial_verified: bool
  scalar_root_verified: bool
  axis_boundary_verified: bool
  selected_shape_scale: float | None
  selected_residual: float | None
  minimum_absolute_residual: float | None
  selected_candidate_measurement: MocFirstCellCandidateMeasurement | None
  selected_field_measurement: MocPhysicalFieldChainMeasurement | None
  selected_field_audit_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  external_validation_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_isolation_verified: bool
  physical_closure_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.selected_field_audit_verified, bool):
      raise TypeError('selected_field_audit_verified must be a bool')
  ####

  @property
  def converged(self) -> bool:
    """Whether the correction record passed this independent audit."""

    return self.status is MocFirstCellFreeBoundaryCorrectionMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'correction_status': self.correction_status,
      'sample_count': self.sample_count,
      'trial_count': self.trial_count,
      'shape_parameter_name': self.shape_parameter_name,
      'shape_family_verified': self.shape_family_verified,
      'trial_residuals_verified': self.trial_residuals_verified,
      'selected_trial_verified': self.selected_trial_verified,
      'scalar_root_verified': self.scalar_root_verified,
      'axis_boundary_verified': self.axis_boundary_verified,
      'selected_shape_scale': self.selected_shape_scale,
      'selected_residual': self.selected_residual,
      'minimum_absolute_residual': self.minimum_absolute_residual,
      'selected_candidate_measurement': (
        None
        if self.selected_candidate_measurement is None
        else self.selected_candidate_measurement.as_report()
      ),
      'selected_field_measurement': (
        None
        if self.selected_field_measurement is None
        else self.selected_field_measurement.as_report()
      ),
      'selected_field_audit_verified': self.selected_field_audit_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'message': self.message,
    }
  ####


def _first_cell_free_boundary_measurement_failure(
  status: MocFirstCellFreeBoundaryCorrectionMeasurementStatus,
  *,
  correction_status: str,
  sample_count: int = 0,
  trial_count: int = 0,
  shape_parameter_name: str = '',
  shape_family_verified: bool = False,
  trial_residuals_verified: bool = False,
  selected_trial_verified: bool = False,
  scalar_root_verified: bool = False,
  axis_boundary_verified: bool = False,
  selected_shape_scale: float | None = None,
  selected_residual: float | None = None,
  minimum_absolute_residual: float | None = None,
  selected_candidate_measurement: MocFirstCellCandidateMeasurement | None = None,
  selected_field_measurement: MocPhysicalFieldChainMeasurement | None = None,
  selected_field_audit_verified: bool = False,
  canonical_free_boundary_verified: bool = False,
  canonical_euler_verified: bool = False,
  external_validation_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_isolation_verified: bool = False,
  physical_closure_verified: bool = False,
  message: str,
) -> MocFirstCellFreeBoundaryCorrectionMeasurement:
  return MocFirstCellFreeBoundaryCorrectionMeasurement(
    status=status,
    correction_status=correction_status,
    sample_count=sample_count,
    trial_count=trial_count,
    shape_parameter_name=shape_parameter_name,
    shape_family_verified=shape_family_verified,
    trial_residuals_verified=trial_residuals_verified,
    selected_trial_verified=selected_trial_verified,
    scalar_root_verified=scalar_root_verified,
    axis_boundary_verified=axis_boundary_verified,
    selected_shape_scale=selected_shape_scale,
    selected_residual=selected_residual,
    minimum_absolute_residual=minimum_absolute_residual,
    selected_candidate_measurement=selected_candidate_measurement,
    selected_field_measurement=selected_field_measurement,
    selected_field_audit_verified=selected_field_audit_verified,
    canonical_free_boundary_verified=canonical_free_boundary_verified,
    canonical_euler_verified=canonical_euler_verified,
    external_validation_verified=external_validation_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=physical_closure_verified,
    message=message,
  )
####


def _correction_measurement_close(
  actual: float,
  expected: float,
  tolerance: float,
) -> bool:
  return bool(
    isfinite(float(actual))
    and isfinite(float(expected))
    and abs(float(actual) - float(expected))
    <= tolerance * max(1.0, abs(float(actual)), abs(float(expected)))
  )
####


def _remeasure_correction_axis_closure(
  trial: object,
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
  pressure_tolerance: float,
) -> tuple[float, bool, bool] | None:
  """Recompute the axis residual from retained trial data only."""

  candidate = getattr(trial, 'candidate', None)
  march = None if candidate is None else candidate.ambient_march
  reported_axis = getattr(trial, 'axis_closure', None)
  if march is None or not march.converged or not march.boundary_samples:
    return None
  if reported_axis is None or reported_axis.ambient_pressure_Pa is None:
    return None
  source = march.boundary_samples[-1]
  try:
    axis = centerline_characteristic_point(
      source.state,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  axis_candidate_verified = bool(
    axis.converged
    and axis.point_m is not None
    and axis.state is not None
    and abs(axis.point_m[1]) <= position_tolerance_m
    and abs(axis.state.theta_rad) <= invariant_tolerance
  )
  if not axis_candidate_verified or axis.state is None or axis.point_m is None:
    return None
  axis_static = _static_pressure_from_total_pressure_for_measurement(
    axis.state,
    source.total_pressure_Pa,
  )
  ambient_pressure = float(reported_axis.ambient_pressure_Pa)
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return None
  residual = (axis_static - ambient_pressure) / ambient_pressure
  try:
    axis_boundary = validate_ambient_pressure_boundary(
      (
        *march.boundary_samples,
        MocAmbientBoundarySample(
          point_m=axis.point_m,
          state=axis.state,
          total_pressure_Pa=source.total_pressure_Pa,
        ),
      ),
      ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  return float(residual), bool(axis_boundary.converged), axis_candidate_verified
####


def measure_first_cell_free_boundary_correction(
  correction: MocFirstCellFreeBoundaryCorrectionResult,
  *,
  shape_tolerance: float = 1.0e-6,
  pressure_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-8,
) -> MocFirstCellFreeBoundaryCorrectionMeasurement:
  """Independently remeasure the shape family and axis residual trials.

  The operator does not call the correction solver or its axis-probe helper.
  It reconstructs each expected axial homothety, recomputes the centerline
  pressure residual from the retained ambient-boundary sample, and invokes the
  existing independent first-cell candidate measurement for the selected
  local field.
  """

  if not isinstance(correction, MocFirstCellFreeBoundaryCorrectionResult):
    return _first_cell_free_boundary_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionMeasurementStatus.INVALID_INPUT,
      correction_status='invalid-input',
      message='correction must be a MocFirstCellFreeBoundaryCorrectionResult',
    )
  try:
    shape_tolerance_value = float(shape_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    position_tolerance_value = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
  except (TypeError, ValueError):
    return _first_cell_free_boundary_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionMeasurementStatus.INVALID_INPUT,
      correction_status=correction.status.value,
      message='correction measurement tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      shape_tolerance_value,
      pressure_tolerance_value,
      position_tolerance_value,
      invariant_tolerance_value,
    )
  ):
    raise ValueError('correction measurement tolerances must be finite and positive')

  initial_points = correction.initial_shock_points_m
  shape_family_verified = bool(
    len(initial_points) >= 3
    and all(
      len(point) == 2 and all(isfinite(float(value)) for value in point)
      for point in initial_points
    )
  )
  trial_residuals_verified = True
  measured_residuals: list[float] = []
  for trial in correction.trials:
    expected_points = tuple(
      (
        initial_points[0][0]
        + trial.shape_scale * (point[0] - initial_points[0][0]),
        point[1],
      )
      for point in initial_points
    ) if shape_family_verified else ()
    points_match = bool(
      len(trial.shock_points_m) == len(expected_points)
      and all(
        hypot(actual[0] - expected[0], actual[1] - expected[1])
        <= position_tolerance_value
        for actual, expected in zip(
          trial.shock_points_m,
          expected_points,
          strict=True,
        )
      )
    )
    shape_family_verified = shape_family_verified and points_match
    candidate = trial.candidate
    if candidate is not None:
      shape_family_verified = shape_family_verified and bool(
        len(candidate.initial_shock_points_m) == len(expected_points)
        and all(
          hypot(actual[0] - expected[0], actual[1] - expected[1])
          <= position_tolerance_value
          for actual, expected in zip(
            candidate.initial_shock_points_m,
            expected_points,
            strict=True,
          )
        )
      )
    if trial.axis_closure is None:
      trial_residuals_verified = trial_residuals_verified and trial.residual is None
      continue
    recomputed = _remeasure_correction_axis_closure(
      trial,
      position_tolerance_m=position_tolerance_value,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
    )
    if recomputed is None or trial.residual is None:
      trial_residuals_verified = False
      continue
    recomputed_residual, recomputed_axis_boundary, recomputed_axis_candidate = recomputed
    measured_residuals.append(recomputed_residual)
    trial_residuals_verified = trial_residuals_verified and bool(
      _correction_measurement_close(
        trial.residual,
        recomputed_residual,
        pressure_tolerance_value,
      )
      and trial.axis_closure.axis_candidate_verified == recomputed_axis_candidate
      and trial.axis_closure.axis_boundary_verified == recomputed_axis_boundary
      and trial.axis_closure.relative_pressure_residual is not None
      and _correction_measurement_close(
        trial.axis_closure.relative_pressure_residual,
        recomputed_residual,
        pressure_tolerance_value,
      )
    )

  selected_trial = None
  if correction.selected_shape_scale is not None:
    selected_trial = next(
      (
        trial
        for trial in correction.trials
        if _correction_measurement_close(
          trial.shape_scale,
          correction.selected_shape_scale,
          shape_tolerance_value,
        )
      ),
      None,
    )
  selected_trial_verified = bool(
    selected_trial is not None
    and (
      (correction.selected_candidate is None and selected_trial.candidate is None)
      or (
        correction.selected_candidate is not None
        and selected_trial.candidate is not None
        and correction.selected_candidate.status
        is selected_trial.candidate.status
        and len(correction.selected_candidate.shock_points_m)
        == len(selected_trial.candidate.shock_points_m)
        and all(
          hypot(actual[0] - expected[0], actual[1] - expected[1])
          <= position_tolerance_value
          for actual, expected in zip(
            correction.selected_candidate.shock_points_m,
            selected_trial.candidate.shock_points_m,
            strict=True,
          )
        )
      )
    )
    and (
      (correction.selected_axis_closure is None and selected_trial.axis_closure is None)
      or (
        correction.selected_axis_closure is not None
        and selected_trial.axis_closure is not None
        and correction.selected_axis_closure.axis_candidate_verified
        == selected_trial.axis_closure.axis_candidate_verified
        and correction.selected_axis_closure.axis_boundary_verified
        == selected_trial.axis_closure.axis_boundary_verified
      )
    )
  )

  selected_candidate_measurement = None
  if correction.selected_candidate is not None:
    selected_candidate_measurement = measure_first_cell_geometry_owned_candidate(
      correction.selected_candidate,
      pressure_residual_tolerance=pressure_tolerance_value,
      position_tolerance_m=position_tolerance_value,
    )
  selected_field_measurement = None
  if (
    correction.selected_candidate is not None
    and correction.selected_candidate.field is not None
  ):
    selected_field_measurement = measure_moc_ambient_closed_physical_field_chain(
      (correction.selected_candidate.field,),
      position_tolerance_m=position_tolerance_value,
      state_tolerance=invariant_tolerance_value,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      tangent_tolerance=pressure_tolerance_value,
    )
  selected_field_audit_verified = bool(
    selected_field_measurement is not None
    and selected_field_measurement.converged
    and selected_field_measurement.physical_closure_verified
    and selected_field_measurement.chain_promotion_blocked
    and selected_field_measurement.production_claim_allowed is False
  )
  selected_residual = (
    None
    if selected_trial is None
    else selected_trial.residual
  )
  minimum_absolute_residual = (
    min((abs(value) for value in measured_residuals), default=None)
  )
  scalar_root_verified = bool(
    correction.status
    in (
      MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_LOCAL_PHYSICAL_BOUNDARY,
      MocFirstCellFreeBoundaryCorrectionStatus.CONVERGED_SCALAR_AXIS_PRESSURE,
    )
    and selected_trial_verified
    and selected_residual is not None
    and abs(selected_residual) <= correction.closure_pressure_tolerance
    and selected_candidate_measurement is not None
    and selected_candidate_measurement.converged
  )
  if correction.status is MocFirstCellFreeBoundaryCorrectionStatus.NO_BRACKET:
    bracket = correction.shape_parameter_bracket
    endpoint_trials = () if bracket is None else tuple(
      trial
      for trial in correction.trials
      if _correction_measurement_close(
        trial.shape_scale,
        bracket[0],
        shape_tolerance_value,
      )
      or _correction_measurement_close(
        trial.shape_scale,
        bracket[1],
        shape_tolerance_value,
      )
    )
    scalar_root_verified = bool(
      len(endpoint_trials) >= 2
      and all(trial.residual is not None for trial in endpoint_trials[:2])
      and endpoint_trials[0].residual is not None
      and endpoint_trials[1].residual is not None
      and endpoint_trials[0].residual * endpoint_trials[1].residual > 0.0
      and all(
        abs(trial.residual) > correction.closure_pressure_tolerance
        for trial in endpoint_trials[:2]
        if trial.residual is not None
      )
    )
  fidelity_isolation_verified = bool(
    correction.canonical_free_boundary_verified is False
    and correction.canonical_euler_verified is False
    and correction.external_validation_verified is False
    and correction.chain_promotion_blocked
    and correction.production_claim_allowed is False
  )
  axis_boundary_verified = bool(
    selected_trial is not None
    and selected_trial.axis_closure is not None
    and _remeasure_correction_axis_closure(
      selected_trial,
      position_tolerance_m=position_tolerance_value,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
    ) is not None
    and selected_trial.axis_closure.axis_boundary_verified
  )
  physical_closure_verified = bool(
    correction.converged
    and scalar_root_verified
    and axis_boundary_verified
    and selected_candidate_measurement is not None
    and selected_candidate_measurement.physical_closure_verified
    and selected_field_audit_verified
  )
  if not shape_family_verified:
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.GEOMETRY_FAILURE
    message = 'returned shape trials do not reproduce the declared axial family'
  elif not trial_residuals_verified:
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.TRIAL_FAILURE
    message = 'returned axis residuals do not reproduce independent trial measurements'
  elif (
    correction.selected_candidate is not None
    and correction.selected_candidate.field is not None
    and not selected_field_audit_verified
  ):
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.FIELD_FAILURE
    message = 'selected physical field failed its independent raw-mesh audit'
  elif not selected_trial_verified or not fidelity_isolation_verified:
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.RESIDUAL_FAILURE
    message = 'selected correction trial or fidelity isolation metadata is inconsistent'
  elif correction.converged and not scalar_root_verified:
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.RESIDUAL_FAILURE
    message = 'correction reports convergence without an independently verified scalar root'
  else:
    status = MocFirstCellFreeBoundaryCorrectionMeasurementStatus.CONVERGED
    message = (
      'independent shape-family, axis-residual, selected-trial, and fidelity '
      'measurement passed; a no-bracket result remains an explicit open '
      'free-boundary condition'
    )
  return _first_cell_free_boundary_measurement_failure(
    status,
    correction_status=correction.status.value,
    sample_count=len(initial_points),
    trial_count=len(correction.trials),
    shape_parameter_name=correction.shape_parameter_name,
    shape_family_verified=shape_family_verified,
    trial_residuals_verified=trial_residuals_verified,
    selected_trial_verified=selected_trial_verified,
    scalar_root_verified=scalar_root_verified,
    axis_boundary_verified=axis_boundary_verified,
    selected_shape_scale=correction.selected_shape_scale,
    selected_residual=selected_residual,
    minimum_absolute_residual=minimum_absolute_residual,
    selected_candidate_measurement=selected_candidate_measurement,
    selected_field_measurement=selected_field_measurement,
    selected_field_audit_verified=selected_field_audit_verified,
    canonical_free_boundary_verified=correction.canonical_free_boundary_verified,
    canonical_euler_verified=correction.canonical_euler_verified,
    external_validation_verified=correction.external_validation_verified,
    chain_promotion_blocked=correction.chain_promotion_blocked,
    production_claim_allowed=correction.production_claim_allowed,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=physical_closure_verified,
    message=message,
  )
####


class MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus(str, Enum):
  """Outcome of independently measuring correction resolution cases."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'correction_refinement_case_failure'
  CONSISTENCY_FAILURE = 'correction_refinement_consistency_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellFreeBoundaryCorrectionRefinementMeasurement:
  """Independent resolution audit for first-cell correction results.

  A converged refinement measurement means that every supplied correction
  outcome was independently measured and that the declared resolution,
  shape-family, residual, and fidelity metadata are mutually consistent.  It
  does not turn a repeated no-bracket result into a free-boundary solution.
  """

  status: MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus
  sample_counts: tuple[int, ...] = ()
  case_measurements: tuple[
    MocFirstCellFreeBoundaryCorrectionMeasurement,
    ...
  ] = ()
  expected_sample_counts: tuple[int, ...] | None = None
  expected_correction_status: str | None = None
  shape_parameter_name: str = ''
  shape_parameter_bracket: tuple[float, float] | None = None
  sample_count_order_verified: bool = False
  expected_sample_counts_verified: bool = False
  shape_family_verified: bool = False
  shape_bracket_verified: bool = False
  outcome_consistency_verified: bool = False
  residuals_verified: bool = False
  residual_values: tuple[float, ...] = ()
  minimum_absolute_residual: float | None = None
  maximum_absolute_residual: float | None = None
  residual_spread: float | None = None
  residual_spread_tolerance: float = 1.0e-6
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  fidelity_isolation_verified: bool = False
  physical_closure_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus'
      )
    sample_counts = tuple(self.sample_counts)
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in sample_counts
    ):
      raise ValueError('sample_counts must contain nonnegative integers')
    object.__setattr__(self, 'sample_counts', sample_counts)
    case_measurements = tuple(self.case_measurements)
    if any(
      not isinstance(
        measurement,
        MocFirstCellFreeBoundaryCorrectionMeasurement,
      )
      for measurement in case_measurements
    ):
      raise TypeError(
        'case_measurements must contain correction measurement values'
      )
    if len(case_measurements) != len(sample_counts):
      raise ValueError(
        'case_measurements must have one entry per sample count'
      )
    object.__setattr__(self, 'case_measurements', case_measurements)
    if self.expected_sample_counts is not None:
      expected_counts = tuple(self.expected_sample_counts)
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in expected_counts
      ):
        raise ValueError(
          'expected_sample_counts must contain nonnegative integers'
        )
      object.__setattr__(self, 'expected_sample_counts', expected_counts)
    if self.expected_correction_status is not None:
      object.__setattr__(
        self,
        'expected_correction_status',
        str(self.expected_correction_status),
      )
    object.__setattr__(self, 'shape_parameter_name', str(self.shape_parameter_name))
    if self.shape_parameter_bracket is not None:
      bracket = tuple(float(value) for value in self.shape_parameter_bracket)
      if (
        len(bracket) != 2
        or not all(isfinite(value) and value > 0.0 for value in bracket)
        or bracket[0] >= bracket[1]
      ):
        raise ValueError(
          'shape_parameter_bracket must contain two ordered positive values'
        )
      object.__setattr__(self, 'shape_parameter_bracket', bracket)
    residual_values = tuple(float(value) for value in self.residual_values)
    if any(not isfinite(value) for value in residual_values):
      raise ValueError('residual_values must be finite')
    object.__setattr__(self, 'residual_values', residual_values)
    for name in (
      'sample_count_order_verified',
      'expected_sample_counts_verified',
      'shape_family_verified',
      'shape_bracket_verified',
      'outcome_consistency_verified',
      'residuals_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_isolation_verified',
      'physical_closure_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    residual_tolerance = float(self.residual_spread_tolerance)
    if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
      raise ValueError('residual_spread_tolerance must be finite and positive')
    object.__setattr__(self, 'residual_spread_tolerance', residual_tolerance)
    for name in (
      'minimum_absolute_residual',
      'maximum_absolute_residual',
      'residual_spread',
    ):
      value = getattr(self, name)
      if value is not None:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        object.__setattr__(self, name, normalized)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether all correction resolution cases passed this audit."""

    return self.status is (
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CONVERGED
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_FIRST_CELL_FREE_BOUNDARY_CORRECTION_REFINEMENT_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'sample_counts': self.sample_counts,
      'expected_sample_counts': self.expected_sample_counts,
      'expected_correction_status': self.expected_correction_status,
      'shape_parameter_name': self.shape_parameter_name,
      'shape_parameter_bracket': self.shape_parameter_bracket,
      'sample_count_order_verified': self.sample_count_order_verified,
      'expected_sample_counts_verified': self.expected_sample_counts_verified,
      'shape_family_verified': self.shape_family_verified,
      'shape_bracket_verified': self.shape_bracket_verified,
      'outcome_consistency_verified': self.outcome_consistency_verified,
      'residuals_verified': self.residuals_verified,
      'residual_values': self.residual_values,
      'minimum_absolute_residual': self.minimum_absolute_residual,
      'maximum_absolute_residual': self.maximum_absolute_residual,
      'residual_spread': self.residual_spread,
      'residual_spread_tolerance': self.residual_spread_tolerance,
      'case_measurements': tuple(
        measurement.as_report() for measurement in self.case_measurements
      ),
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'message': self.message,
    }
  ####


def _first_cell_free_boundary_refinement_measurement_failure(
  status: MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus,
  *,
  message: str,
  sample_counts: Sequence[int] = (),
  case_measurements: Sequence[
    MocFirstCellFreeBoundaryCorrectionMeasurement
  ] = (),
  expected_sample_counts: Sequence[int] | None = None,
  expected_correction_status: str | None = None,
  shape_parameter_name: str = '',
  shape_parameter_bracket: tuple[float, float] | None = None,
  sample_count_order_verified: bool = False,
  expected_sample_counts_verified: bool = False,
  shape_family_verified: bool = False,
  shape_bracket_verified: bool = False,
  outcome_consistency_verified: bool = False,
  residuals_verified: bool = False,
  residual_values: Sequence[float] = (),
  minimum_absolute_residual: float | None = None,
  maximum_absolute_residual: float | None = None,
  residual_spread: float | None = None,
  residual_spread_tolerance: float = 1.0e-6,
  canonical_free_boundary_verified: bool = False,
  canonical_euler_verified: bool = False,
  external_validation_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_isolation_verified: bool = False,
  physical_closure_verified: bool = False,
) -> MocFirstCellFreeBoundaryCorrectionRefinementMeasurement:
  return MocFirstCellFreeBoundaryCorrectionRefinementMeasurement(
    status=status,
    sample_counts=tuple(sample_counts),
    case_measurements=tuple(case_measurements),
    expected_sample_counts=(
      None
      if expected_sample_counts is None
      else tuple(expected_sample_counts)
    ),
    expected_correction_status=expected_correction_status,
    shape_parameter_name=shape_parameter_name,
    shape_parameter_bracket=shape_parameter_bracket,
    sample_count_order_verified=sample_count_order_verified,
    expected_sample_counts_verified=expected_sample_counts_verified,
    shape_family_verified=shape_family_verified,
    shape_bracket_verified=shape_bracket_verified,
    outcome_consistency_verified=outcome_consistency_verified,
    residuals_verified=residuals_verified,
    residual_values=tuple(residual_values),
    minimum_absolute_residual=minimum_absolute_residual,
    maximum_absolute_residual=maximum_absolute_residual,
    residual_spread=residual_spread,
    residual_spread_tolerance=residual_spread_tolerance,
    canonical_free_boundary_verified=canonical_free_boundary_verified,
    canonical_euler_verified=canonical_euler_verified,
    external_validation_verified=external_validation_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=physical_closure_verified,
    message=message,
  )
####


def measure_first_cell_free_boundary_correction_refinement(
  corrections: Sequence[MocFirstCellFreeBoundaryCorrectionResult],
  *,
  expected_sample_counts: Sequence[int] | None = None,
  expected_status: MocFirstCellFreeBoundaryCorrectionStatus | None = None,
  shape_tolerance: float = 1.0e-6,
  pressure_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-8,
  residual_spread_tolerance: float = 1.0e-6,
) -> MocFirstCellFreeBoundaryCorrectionRefinementMeasurement:
  """Independently measure a fixed-configuration correction refinement."""

  try:
    items = tuple(corrections)
  except TypeError:
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
      message='corrections must be an iterable of correction results',
    )
  if not items or any(
    not isinstance(item, MocFirstCellFreeBoundaryCorrectionResult)
    for item in items
  ):
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
      message=(
        'corrections must contain at least one '
        'MocFirstCellFreeBoundaryCorrectionResult'
      ),
    )
  if expected_status is not None and not isinstance(
    expected_status,
    MocFirstCellFreeBoundaryCorrectionStatus,
  ):
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
      message='expected_status must be a correction status or None',
    )
  try:
    shape_tolerance_value = float(shape_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    position_tolerance_value = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    residual_spread_tolerance_value = float(residual_spread_tolerance)
  except (TypeError, ValueError):
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
      message='correction refinement tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      shape_tolerance_value,
      pressure_tolerance_value,
      position_tolerance_value,
      invariant_tolerance_value,
      residual_spread_tolerance_value,
    )
  ):
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
      message='correction refinement tolerances must be finite and positive',
    )
  try:
    measured_cases = tuple(
      measure_first_cell_free_boundary_correction(
        item,
        shape_tolerance=shape_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        position_tolerance_m=position_tolerance_value,
        invariant_tolerance=invariant_tolerance_value,
      )
      for item in items
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _first_cell_free_boundary_refinement_measurement_failure(
      MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CASE_FAILURE,
      message=f'independent correction case measurement raised: {error}',
    )
  sample_counts = tuple(len(item.initial_shock_points_m) for item in items)
  normalized_expected_counts = None
  if expected_sample_counts is not None:
    try:
      normalized_expected_counts = tuple(expected_sample_counts)
    except TypeError:
      return _first_cell_free_boundary_refinement_measurement_failure(
        MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
        sample_counts=sample_counts,
        case_measurements=measured_cases,
        message='expected_sample_counts must be an integer sequence',
      )
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in normalized_expected_counts
    ):
      return _first_cell_free_boundary_refinement_measurement_failure(
        MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.INVALID_INPUT,
        sample_counts=sample_counts,
        case_measurements=measured_cases,
        message='expected_sample_counts must contain nonnegative integers',
      )
  sample_count_order_verified = all(
    left < right for left, right in zip(sample_counts, sample_counts[1:])
  )
  expected_sample_counts_verified = bool(
    normalized_expected_counts is None
    or sample_counts == normalized_expected_counts
  )
  first = items[0]
  shape_parameter_name = first.shape_parameter_name
  shape_parameter_bracket = first.shape_parameter_bracket
  shape_bracket_verified = bool(shape_parameter_bracket is not None)
  for item in items[1:]:
    shape_bracket_verified = shape_bracket_verified and bool(
      item.shape_parameter_name == shape_parameter_name
      and item.shape_parameter_bracket is not None
      and shape_parameter_bracket is not None
      and _correction_measurement_close(
        item.shape_parameter_bracket[0],
        shape_parameter_bracket[0],
        shape_tolerance_value,
      )
      and _correction_measurement_close(
        item.shape_parameter_bracket[1],
        shape_parameter_bracket[1],
        shape_tolerance_value,
      )
    )
  shape_family_verified = bool(
    all(measurement.shape_family_verified for measurement in measured_cases)
  )
  statuses = tuple(item.status for item in items)
  expected_status_verified = bool(
    expected_status is None
    or all(status is expected_status for status in statuses)
  )
  outcome_consistency_verified = bool(
    all(status is statuses[0] for status in statuses)
    and expected_status_verified
  )
  residual_values = tuple(
    float(measurement.selected_residual)
    for measurement in measured_cases
    if measurement.selected_residual is not None
  )
  residual_values_verified = bool(
    len(residual_values) == len(items)
    and all(isfinite(value) for value in residual_values)
  )
  residual_spread = (
    None
    if not residual_values
    else max(residual_values) - min(residual_values)
  )
  minimum_absolute_residual = (
    None
    if not residual_values
    else min(abs(value) for value in residual_values)
  )
  maximum_absolute_residual = (
    None
    if not residual_values
    else max(abs(value) for value in residual_values)
  )
  residuals_verified = bool(
    residual_values_verified
    and residual_spread is not None
    and residual_spread <= residual_spread_tolerance_value * max(
      1.0,
      maximum_absolute_residual or 0.0,
    )
  )
  case_audits_verified = all(
    measurement.converged
    and measurement.shape_family_verified
    and measurement.trial_residuals_verified
    and measurement.selected_trial_verified
    and measurement.selected_field_audit_verified
    and measurement.fidelity_isolation_verified
    for measurement in measured_cases
  )
  no_bracket_audit_verified = bool(
    expected_status is not MocFirstCellFreeBoundaryCorrectionStatus.NO_BRACKET
    or all(
      measurement.scalar_root_verified
      and measurement.axis_boundary_verified is False
      and measurement.physical_closure_verified is False
      for measurement in measured_cases
    )
  )
  fidelity_isolation_verified = bool(
    all(
      item.canonical_free_boundary_verified is False
      and item.canonical_euler_verified is False
      and item.external_validation_verified is False
      and item.chain_promotion_blocked
      and item.production_claim_allowed is False
      and measurement.canonical_free_boundary_verified is False
      and measurement.canonical_euler_verified is False
      and measurement.external_validation_verified is False
      and measurement.chain_promotion_blocked
      and measurement.production_claim_allowed is False
      for item, measurement in zip(items, measured_cases, strict=True)
    )
  )
  physical_closure_verified = bool(
    all(
      item.physical_closure_verified
      and measurement.physical_closure_verified
      for item, measurement in zip(items, measured_cases, strict=True)
    )
  )
  all_checks = bool(
    sample_count_order_verified
    and expected_sample_counts_verified
    and shape_bracket_verified
    and shape_family_verified
    and outcome_consistency_verified
    and residuals_verified
    and case_audits_verified
    and no_bracket_audit_verified
    and fidelity_isolation_verified
  )
  if not case_audits_verified:
    status = MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CASE_FAILURE
    message = 'one or more correction cases failed independent measurement'
  elif not all_checks:
    status = MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CONSISTENCY_FAILURE
    message = 'correction resolution cases are not mutually consistent'
  else:
    status = MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CONVERGED
    message = (
      'independent correction-case, resolution-order, fixed-shape, residual, '
      'and fidelity audit passed; repeated boundary outcomes remain research-only'
    )
  return _first_cell_free_boundary_refinement_measurement_failure(
    status,
    sample_counts=sample_counts,
    case_measurements=measured_cases,
    expected_sample_counts=normalized_expected_counts,
    expected_correction_status=(
      None if expected_status is None else expected_status.value
    ),
    shape_parameter_name=shape_parameter_name,
    shape_parameter_bracket=shape_parameter_bracket,
    sample_count_order_verified=sample_count_order_verified,
    expected_sample_counts_verified=expected_sample_counts_verified,
    shape_family_verified=shape_family_verified,
    shape_bracket_verified=shape_bracket_verified,
    outcome_consistency_verified=outcome_consistency_verified,
    residuals_verified=residuals_verified,
    residual_values=residual_values,
    minimum_absolute_residual=minimum_absolute_residual,
    maximum_absolute_residual=maximum_absolute_residual,
    residual_spread=residual_spread,
    residual_spread_tolerance=residual_spread_tolerance_value,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=fidelity_isolation_verified,
    production_claim_allowed=False,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=physical_closure_verified,
    message=message,
  )
####


class MocFirstCellResearchChainMeasurementStatus(str, Enum):
  """Outcome of independently auditing a first-cell-to-chain handoff."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  CANDIDATE_FAILURE = 'candidate_measurement_failure'
  CHAIN_FAILURE = 'continued_chain_measurement_failure'
  FIELD_CHAIN_FAILURE = 'physical_field_chain_measurement_failure'
  CONSISTENCY_FAILURE = 'handoff_consistency_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellResearchChainMeasurement:
  """Independent evidence for a local first-cell research continuation.

  The operator receives the candidate, planner trace, and retained physical
  fields separately.  It remeasures each component and checks that the exact
  candidate field is the first field in the chain, that at least one fresh
  continuation was accepted, and that the planner and physical-field audits
  agree on every handoff.  A passing result is still research evidence only.
  """

  status: MocFirstCellResearchChainMeasurementStatus
  operator_id: str = MOC_FIRST_CELL_RESEARCH_CHAIN_OPERATOR_ID
  planner_kind: str | None = None
  candidate_status: str | None = None
  field_count: int = 0
  continued_cell_count: int = 0
  candidate_measurement: MocFirstCellCandidateMeasurement | None = None
  chain_planner_measurement: 'MocChainPlannerMeasurement | None' = None
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None
  first_cell_field_identity_verified: bool = False
  candidate_handoff_verified: bool = False
  continued_cell_count_verified: bool = False
  handoff_links_verified: bool | None = None
  research_chain_resolved: bool = False
  physical_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocFirstCellResearchChainMeasurementStatus,
    ):
      raise TypeError(
        'status must be a MocFirstCellResearchChainMeasurementStatus'
      )
    for name in ('field_count', 'continued_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.candidate_measurement is not None and not isinstance(
      self.candidate_measurement,
      MocFirstCellCandidateMeasurement,
    ):
      raise TypeError(
        'candidate_measurement must be a MocFirstCellCandidateMeasurement or None'
      )
    if self.chain_planner_measurement is not None and not isinstance(
      self.chain_planner_measurement,
      MocChainPlannerMeasurement,
    ):
      raise TypeError(
        'chain_planner_measurement must be a MocChainPlannerMeasurement or None'
      )
    if self.physical_field_chain_measurement is not None and not isinstance(
      self.physical_field_chain_measurement,
      MocPhysicalFieldChainMeasurement,
    ):
      raise TypeError(
        'physical_field_chain_measurement must be a '
        'MocPhysicalFieldChainMeasurement or None'
      )
    for name in (
      'first_cell_field_identity_verified',
      'candidate_handoff_verified',
      'continued_cell_count_verified',
      'research_chain_resolved',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.handoff_links_verified is not None and not isinstance(
      self.handoff_links_verified,
      bool,
    ):
      raise TypeError('handoff_links_verified must be a bool or None')
    object.__setattr__(self, 'planner_kind', (
      None if self.planner_kind is None else str(self.planner_kind)
    ))
    object.__setattr__(self, 'candidate_status', (
      None if self.candidate_status is None else str(self.candidate_status)
    ))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocFirstCellResearchChainMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'planner_kind': self.planner_kind,
      'candidate_status': self.candidate_status,
      'counts': {
        'physical_fields': self.field_count,
        'continued_cells': self.continued_cell_count,
      },
      'checks': {
        'first_cell_field_identity_verified': (
          self.first_cell_field_identity_verified
        ),
        'candidate_handoff_verified': self.candidate_handoff_verified,
        'continued_cell_count_verified': self.continued_cell_count_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'research_chain_resolved': self.research_chain_resolved,
        'physical_closure_verified': self.physical_closure_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'candidate_measurement': (
        None
        if self.candidate_measurement is None
        else self.candidate_measurement.as_report()
      ),
      'chain_planner_measurement': (
        None
        if self.chain_planner_measurement is None
        else self.chain_planner_measurement.as_report()
      ),
      'physical_field_chain_measurement': (
        None
        if self.physical_field_chain_measurement is None
        else self.physical_field_chain_measurement.as_report()
      ),
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####


def _first_cell_research_chain_measurement_failure(
  status: MocFirstCellResearchChainMeasurementStatus,
  *,
  planner_kind: str | None = None,
  candidate_status: str | None = None,
  field_count: int = 0,
  continued_cell_count: int = 0,
  candidate_measurement: MocFirstCellCandidateMeasurement | None = None,
  chain_planner_measurement: 'MocChainPlannerMeasurement | None' = None,
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None,
  first_cell_field_identity_verified: bool = False,
  candidate_handoff_verified: bool = False,
  continued_cell_count_verified: bool = False,
  handoff_links_verified: bool | None = None,
  research_chain_resolved: bool = False,
  physical_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  message: str,
) -> MocFirstCellResearchChainMeasurement:
  return MocFirstCellResearchChainMeasurement(
    status=status,
    planner_kind=planner_kind,
    candidate_status=candidate_status,
    field_count=field_count,
    continued_cell_count=continued_cell_count,
    candidate_measurement=candidate_measurement,
    chain_planner_measurement=chain_planner_measurement,
    physical_field_chain_measurement=physical_field_chain_measurement,
    first_cell_field_identity_verified=first_cell_field_identity_verified,
    candidate_handoff_verified=candidate_handoff_verified,
    continued_cell_count_verified=continued_cell_count_verified,
    handoff_links_verified=handoff_links_verified,
    research_chain_resolved=research_chain_resolved,
    physical_closure_verified=physical_closure_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


def measure_first_cell_geometry_owned_research_chain(
  candidate: MocFirstCellCandidateResult,
  planner: MocChainPlannerResult | None,
  physical_fields: Sequence[MocPhysicalPostShockFieldResult],
  *,
  shock_residual_tolerance_rad: float = 1.0e-8,
  pressure_residual_tolerance: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-8,
) -> MocFirstCellResearchChainMeasurement:
  """Independently audit a candidate field and its continued-chain prefix.

  The operator never calls a planner or solver.  It remeasures the candidate,
  planner trace, and every retained physical field, then verifies that the
  candidate object itself is the exact first field and that at least one
  downstream cell was accepted with matching handoff links.
  """

  if not isinstance(candidate, MocFirstCellCandidateResult):
    return _first_cell_research_chain_measurement_failure(
      MocFirstCellResearchChainMeasurementStatus.INVALID_INPUT,
      message='candidate must be a MocFirstCellCandidateResult',
    )
  if planner is not None and not isinstance(planner, MocChainPlannerResult):
    return _first_cell_research_chain_measurement_failure(
      MocFirstCellResearchChainMeasurementStatus.INVALID_INPUT,
      candidate_status=candidate.status.value,
      message='planner must be a MocChainPlannerResult or None',
    )
  try:
    fields = tuple(physical_fields)
  except TypeError:
    return _first_cell_research_chain_measurement_failure(
      MocFirstCellResearchChainMeasurementStatus.INVALID_INPUT,
      planner_kind=(None if planner is None else planner.planner_kind.value),
      candidate_status=candidate.status.value,
      message='physical_fields must be an iterable of physical field results',
    )
  if any(not isinstance(field, MocPhysicalPostShockFieldResult) for field in fields):
    return _first_cell_research_chain_measurement_failure(
      MocFirstCellResearchChainMeasurementStatus.INVALID_INPUT,
      planner_kind=(None if planner is None else planner.planner_kind.value),
      candidate_status=candidate.status.value,
      field_count=len(fields),
      message='physical_fields must contain only physical post-shock fields',
    )
  for name, value in (
    ('shock_residual_tolerance_rad', shock_residual_tolerance_rad),
    ('pressure_residual_tolerance', pressure_residual_tolerance),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  candidate_measurement = measure_first_cell_geometry_owned_candidate(
    candidate,
    shock_residual_tolerance_rad=shock_residual_tolerance_rad,
    pressure_residual_tolerance=pressure_residual_tolerance,
    position_tolerance_m=position_tolerance_m,
  )
  chain_planner_measurement = None
  if planner is not None:
    chain_planner_measurement = measure_moc_chain_planner(
      planner,
      position_tolerance_m=position_tolerance_m,
    )
  physical_field_chain_measurement = None
  if fields:
    physical_field_chain_measurement = measure_moc_ambient_closed_physical_field_chain(
      fields,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_residual_tolerance,
      tangent_tolerance=pressure_residual_tolerance,
    )

  planner_kind = None if planner is None else planner.planner_kind.value
  candidate_status = candidate.status.value
  continued_cell_count = (
    0 if planner is None else max(0, planner.chain.cell_count - 1)
  )
  first_cell_field_identity_verified = bool(
    candidate.field is not None
    and fields
    and fields[0] is candidate.field
  )
  candidate_handoff_verified = bool(
    first_cell_field_identity_verified
    and candidate.local_physical_closure_verified
    and candidate_measurement.converged
    and candidate_measurement.physical_closure_verified
  )
  continued_cell_count_verified = bool(
    planner is not None
    and continued_cell_count >= 1
    and planner.chain.cell_count == len(fields)
  )
  planner_verified = bool(
    chain_planner_measurement is not None
    and chain_planner_measurement.converged
    and chain_planner_measurement.termination_verified
    and chain_planner_measurement.fidelity_isolation_verified
    and chain_planner_measurement.production_claim_allowed is False
  )
  field_chain_verified = bool(
    physical_field_chain_measurement is not None
    and physical_field_chain_measurement.converged
    and physical_field_chain_measurement.handoff_links_verified is True
    and physical_field_chain_measurement.fresh_domain_verified
    and physical_field_chain_measurement.chain_promotion_blocked
    and physical_field_chain_measurement.production_claim_allowed is False
  )
  handoff_values = tuple(
    value
    for value in (
      None
      if chain_planner_measurement is None
      else chain_planner_measurement.handoff_links_verified,
      None
      if physical_field_chain_measurement is None
      else physical_field_chain_measurement.handoff_links_verified,
    )
    if value is not None
  )
  handoff_links_verified = (
    False if any(value is False for value in handoff_values)
    else True if len(handoff_values) == 2 and all(value is True for value in handoff_values)
    else None
  )
  research_chain_resolved = bool(
    planner is not None
    and continued_cell_count >= 1
    and planner.chain.resolved
  )
  physical_closure_verified = bool(
    physical_field_chain_measurement is not None
    and physical_field_chain_measurement.physical_closure_verified
  )
  fidelity_isolation_verified = bool(
    candidate_measurement.canonical_free_boundary_verified is False
    and candidate_measurement.canonical_euler_verified is False
    and candidate_measurement.external_validation_verified is False
    and candidate_measurement.chain_promotion_blocked
    and candidate_measurement.production_claim_allowed is False
    and (planner is None or planner.production_claim_allowed is False)
    and (
      physical_field_chain_measurement is None
      or (
        physical_field_chain_measurement.chain_promotion_blocked
        and physical_field_chain_measurement.production_claim_allowed is False
      )
    )
  )
  all_checks = bool(
    candidate_handoff_verified
    and continued_cell_count_verified
    and planner_verified
    and field_chain_verified
    and handoff_links_verified is True
    and research_chain_resolved
    and fidelity_isolation_verified
  )
  if not candidate_measurement.converged:
    status = MocFirstCellResearchChainMeasurementStatus.CANDIDATE_FAILURE
    message = (
      'independent first-cell candidate measurement failed before the '
      f'continued-chain audit: {candidate_measurement.message}'
    )
  elif planner is None or not planner_verified or not continued_cell_count_verified:
    status = MocFirstCellResearchChainMeasurementStatus.CHAIN_FAILURE
    message = (
      'continued-chain planner evidence is missing, unresolved, or contains '
      'no accepted cell after the first-cell candidate'
    )
  elif not field_chain_verified:
    status = MocFirstCellResearchChainMeasurementStatus.FIELD_CHAIN_FAILURE
    message = (
      'independent physical-field chain measurement failed exact handoff, '
      'fresh-domain, or local closure checks'
    )
  elif not all_checks:
    status = MocFirstCellResearchChainMeasurementStatus.CONSISTENCY_FAILURE
    message = 'first-cell-to-chain handoff metadata is internally inconsistent'
  else:
    status = MocFirstCellResearchChainMeasurementStatus.CONVERGED
    message = (
      'independent candidate, planner, physical-field, exact-handoff, and '
      'fresh-domain audits passed; canonical free-boundary and product gates '
      'remain closed'
    )
  return _first_cell_research_chain_measurement_failure(
    status,
    planner_kind=planner_kind,
    candidate_status=candidate_status,
    field_count=len(fields),
    continued_cell_count=continued_cell_count,
    candidate_measurement=candidate_measurement,
    chain_planner_measurement=chain_planner_measurement,
    physical_field_chain_measurement=physical_field_chain_measurement,
    first_cell_field_identity_verified=first_cell_field_identity_verified,
    candidate_handoff_verified=candidate_handoff_verified,
    continued_cell_count_verified=continued_cell_count_verified,
    handoff_links_verified=handoff_links_verified,
    research_chain_resolved=research_chain_resolved,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


class MocFirstCellResearchChainRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing repeated, refined first-cell chain runs."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellResearchChainRefinementCase:
  """One independently repeated chain run at a declared field resolution."""

  sample_count: int
  planner: MocFirstCellResearchChainPlannerResult
  repeat_planner: MocFirstCellResearchChainPlannerResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    if not isinstance(
      self.planner,
      MocFirstCellResearchChainPlannerResult,
    ):
      raise TypeError(
        'planner must be a MocFirstCellResearchChainPlannerResult'
      )
    if not isinstance(
      self.repeat_planner,
      MocFirstCellResearchChainPlannerResult,
    ):
      raise TypeError(
        'repeat_planner must be a MocFirstCellResearchChainPlannerResult'
      )
  ####
####


@dataclass(frozen=True, slots=True)
class MocFirstCellResearchChainRefinementMeasurement:
  """Independent refinement and determinism evidence for a chain sequence.

  Each case contains two solver runs at the same declared shock/field
  resolution.  The operator independently remeasures both runs, compares the
  repeated geometry and handoff trace, then compares the primary runs across
  increasing resolutions.  This proves only a stable research prefix; it
  does not close the canonical reflected free boundary or authorize product
  promotion.
  """

  status: MocFirstCellResearchChainRefinementMeasurementStatus
  operator_id: str = MOC_FIRST_CELL_RESEARCH_CHAIN_REFINEMENT_OPERATOR_ID
  cases: tuple[MocFirstCellResearchChainRefinementCase, ...] = ()
  chain_measurements: tuple[MocFirstCellResearchChainMeasurement, ...] = ()
  repeat_chain_measurements: tuple[MocFirstCellResearchChainMeasurement, ...] = ()
  sample_counts: tuple[int, ...] = ()
  expected_cell_count: int | None = None
  cell_count: int | None = None
  sample_count_order_verified: bool = False
  expected_sample_counts_verified: bool = True
  cell_count_consistent: bool = False
  planner_kind_consistent: bool = False
  termination_consistency_verified: bool = False
  geometry_shape_verified: bool = False
  deterministic_repeats_verified: bool = False
  handoff_links_verified: bool | None = None
  physical_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  axial_extent_residuals_m: tuple[float, ...] = ()
  shock_spacing_residuals_m: tuple[float, ...] = ()
  maximum_radius_residuals_m: tuple[float, ...] = ()
  mesh_area_residuals_m2: tuple[float, ...] = ()
  repeat_axial_extent_residuals_m: tuple[float, ...] = ()
  repeat_mesh_area_residuals_m2: tuple[float, ...] = ()
  refinement_convergence_verified: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    measurements = tuple(self.chain_measurements)
    repeat_measurements = tuple(self.repeat_chain_measurements)
    if len(cases) != len(measurements) or len(cases) != len(repeat_measurements):
      raise ValueError(
        'cases and both chain-measurement sequences must have equal lengths'
      )
    if any(
      not isinstance(case, MocFirstCellResearchChainRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain MocFirstCellResearchChainRefinementCase values'
      )
    if any(
      not isinstance(measurement, MocFirstCellResearchChainMeasurement)
      for measurement in (*measurements, *repeat_measurements)
    ):
      raise TypeError(
        'chain measurements must contain '
        'MocFirstCellResearchChainMeasurement values'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'chain_measurements', measurements)
    object.__setattr__(self, 'repeat_chain_measurements', repeat_measurements)
    object.__setattr__(
      self,
      'sample_counts',
      tuple(case.sample_count for case in cases),
    )
    if self.expected_cell_count is not None and (
      isinstance(self.expected_cell_count, bool)
      or not isinstance(self.expected_cell_count, int)
      or self.expected_cell_count < 1
    ):
      raise ValueError('expected_cell_count must be positive when supplied')
    if self.cell_count is not None and (
      isinstance(self.cell_count, bool)
      or not isinstance(self.cell_count, int)
      or self.cell_count < 1
    ):
      raise ValueError('cell_count must be positive when supplied')
    for name in (
      'axial_extent_residuals_m',
      'shock_spacing_residuals_m',
      'maximum_radius_residuals_m',
      'mesh_area_residuals_m2',
      'repeat_axial_extent_residuals_m',
      'repeat_mesh_area_residuals_m2',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'sample_count_order_verified',
      'expected_sample_counts_verified',
      'cell_count_consistent',
      'planner_kind_consistent',
      'termination_consistency_verified',
      'geometry_shape_verified',
      'deterministic_repeats_verified',
      'physical_closure_verified',
      'fidelity_isolation_verified',
      'refinement_convergence_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.handoff_links_verified is not None and not isinstance(
      self.handoff_links_verified,
      bool,
    ):
      raise TypeError('handoff_links_verified must be a bool or None')
  ####

  @property
  def converged(self) -> bool:
    return (
      self.status
      is MocFirstCellResearchChainRefinementMeasurementStatus.CONVERGED
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'sample_counts': list(self.sample_counts),
      'expected_cell_count': self.expected_cell_count,
      'cell_count': self.cell_count,
      'cases': [
        {
          'sample_count': case.sample_count,
          'measurement': measurement.as_report(),
          'repeat_measurement': repeat_measurement.as_report(),
          'repeat_axial_extent_residual_m': (
            self.repeat_axial_extent_residuals_m[index]
            if index < len(self.repeat_axial_extent_residuals_m) else None
          ),
          'repeat_mesh_area_residual_m2': (
            self.repeat_mesh_area_residuals_m2[index]
            if index < len(self.repeat_mesh_area_residuals_m2) else None
          ),
        }
        for index, (case, measurement, repeat_measurement) in enumerate(zip(
          self.cases,
          self.chain_measurements,
          self.repeat_chain_measurements,
          strict=True,
        ))
      ],
      'checks': {
        'sample_count_order_verified': self.sample_count_order_verified,
        'expected_sample_counts_verified': self.expected_sample_counts_verified,
        'cell_count_consistent': self.cell_count_consistent,
        'planner_kind_consistent': self.planner_kind_consistent,
        'termination_consistency_verified': (
          self.termination_consistency_verified
        ),
        'geometry_shape_verified': self.geometry_shape_verified,
        'deterministic_repeats_verified': self.deterministic_repeats_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'refinement_convergence_verified': (
          self.refinement_convergence_verified
        ),
      },
      'residuals': {
        'axial_extent_residuals_m': list(self.axial_extent_residuals_m),
        'shock_spacing_residuals_m': list(self.shock_spacing_residuals_m),
        'maximum_radius_residuals_m': list(self.maximum_radius_residuals_m),
        'mesh_area_residuals_m2': list(self.mesh_area_residuals_m2),
        'repeat_axial_extent_residuals_m': list(
          self.repeat_axial_extent_residuals_m
        ),
        'repeat_mesh_area_residuals_m2': list(
          self.repeat_mesh_area_residuals_m2
        ),
      },
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _first_cell_research_chain_refinement_failure(
  status: MocFirstCellResearchChainRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocFirstCellResearchChainRefinementCase] = (),
  chain_measurements: Sequence[MocFirstCellResearchChainMeasurement] = (),
  repeat_chain_measurements: Sequence[MocFirstCellResearchChainMeasurement] = (),
  expected_cell_count: int | None = None,
  cell_count: int | None = None,
  sample_count_order_verified: bool = False,
  expected_sample_counts_verified: bool = True,
  cell_count_consistent: bool = False,
  planner_kind_consistent: bool = False,
  termination_consistency_verified: bool = False,
  geometry_shape_verified: bool = False,
  deterministic_repeats_verified: bool = False,
  handoff_links_verified: bool | None = None,
  physical_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  axial_extent_residuals_m: Sequence[float] = (),
  shock_spacing_residuals_m: Sequence[float] = (),
  maximum_radius_residuals_m: Sequence[float] = (),
  mesh_area_residuals_m2: Sequence[float] = (),
  repeat_axial_extent_residuals_m: Sequence[float] = (),
  repeat_mesh_area_residuals_m2: Sequence[float] = (),
  refinement_convergence_verified: bool = False,
) -> MocFirstCellResearchChainRefinementMeasurement:
  normalized_cases = tuple(cases)
  normalized_measurements = tuple(chain_measurements)
  normalized_repeat_measurements = tuple(repeat_chain_measurements)
  paired_inputs_are_valid = bool(
    len(normalized_cases) == len(normalized_measurements)
    and len(normalized_cases) == len(normalized_repeat_measurements)
    and all(
      isinstance(case, MocFirstCellResearchChainRefinementCase)
      for case in normalized_cases
    )
    and all(
      isinstance(measurement, MocFirstCellResearchChainMeasurement)
      for measurement in (
        *normalized_measurements,
        *normalized_repeat_measurements,
      )
    )
  )
  if not paired_inputs_are_valid:
    normalized_cases = ()
    normalized_measurements = ()
    normalized_repeat_measurements = ()
  return MocFirstCellResearchChainRefinementMeasurement(
    status=status,
    cases=normalized_cases,
    chain_measurements=normalized_measurements,
    repeat_chain_measurements=normalized_repeat_measurements,
    expected_cell_count=expected_cell_count,
    cell_count=cell_count,
    sample_count_order_verified=sample_count_order_verified,
    expected_sample_counts_verified=expected_sample_counts_verified,
    cell_count_consistent=cell_count_consistent,
    planner_kind_consistent=planner_kind_consistent,
    termination_consistency_verified=termination_consistency_verified,
    geometry_shape_verified=geometry_shape_verified,
    deterministic_repeats_verified=deterministic_repeats_verified,
    handoff_links_verified=handoff_links_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    axial_extent_residuals_m=tuple(axial_extent_residuals_m),
    shock_spacing_residuals_m=tuple(shock_spacing_residuals_m),
    maximum_radius_residuals_m=tuple(maximum_radius_residuals_m),
    mesh_area_residuals_m2=tuple(mesh_area_residuals_m2),
    repeat_axial_extent_residuals_m=tuple(repeat_axial_extent_residuals_m),
    repeat_mesh_area_residuals_m2=tuple(repeat_mesh_area_residuals_m2),
    refinement_convergence_verified=refinement_convergence_verified,
    claim_status='not_accepted',
    message=message,
  )
####


def _research_chain_geometry_metrics(
  measurement: MocFirstCellResearchChainMeasurement,
) -> dict[str, tuple[float, ...]] | None:
  field_chain = measurement.physical_field_chain_measurement
  if field_chain is None or not field_chain.field_measurements:
    return None
  field_measurements = field_chain.field_measurements
  axial_extents: list[float] = []
  shock_starts: list[float] = []
  maximum_radii: list[float] = []
  mesh_areas: list[float] = []
  for field_measurement in field_measurements:
    if (
      field_measurement.axial_extent_m is None
      or field_measurement.shock_start_m is None
      or field_measurement.maximum_radius_m is None
      or field_measurement.mesh_area_m2 is None
    ):
      return None
    axial_extents.extend(float(value) for value in field_measurement.axial_extent_m)
    shock_starts.append(float(field_measurement.shock_start_m[0]))
    maximum_radii.append(float(field_measurement.maximum_radius_m))
    mesh_areas.append(float(field_measurement.mesh_area_m2))
  if not all(
    isfinite(value)
    for values in (axial_extents, shock_starts, maximum_radii, mesh_areas)
    for value in values
  ):
    return None
  shock_spacing = tuple(
    right - left for left, right in zip(shock_starts, shock_starts[1:])
  )
  return {
    'axial_extents': tuple(axial_extents),
    'shock_spacing': shock_spacing,
    'maximum_radii': tuple(maximum_radii),
    'mesh_areas': tuple(mesh_areas),
  }
####


def _maximum_sequence_residual(
  left: Sequence[float],
  right: Sequence[float],
) -> float | None:
  if len(left) != len(right):
    return None
  values = tuple(abs(float(current) - float(previous)) for previous, current in zip(
    left,
    right,
    strict=True,
  ))
  return max(values, default=0.0)
####


def _research_chain_step_signature(
  result: MocFirstCellResearchChainPlannerResult,
) -> tuple[tuple[object, ...], ...] | None:
  planner = result.chain_planner
  if planner is None:
    return None
  return tuple(
    (
      step.current_cell_index,
      step.next_cell_index,
      step.result_kind,
      step.result_status,
      step.result_termination_reason,
      step.incoming_handoff_fingerprint,
      step.result_handoff_fingerprint,
      step.result_consumed_handoff_fingerprint,
      step.result_end_x_m,
    )
    for step in planner.steps
  )
####


def _research_chain_repeat_verified(
  primary: MocFirstCellResearchChainPlannerResult,
  repeat: MocFirstCellResearchChainPlannerResult,
  primary_measurement: MocFirstCellResearchChainMeasurement,
  repeat_measurement: MocFirstCellResearchChainMeasurement,
  *,
  position_tolerance_m: float,
  area_tolerance_m2: float,
) -> tuple[bool, float | None, float | None]:
  primary_metrics = _research_chain_geometry_metrics(primary_measurement)
  repeat_metrics = _research_chain_geometry_metrics(repeat_measurement)
  if primary_metrics is None or repeat_metrics is None:
    return False, None, None
  if (
    primary.planner_kind is not repeat.planner_kind
    or primary.termination.reason is not repeat.termination.reason
    or primary.termination.physical_termination
    != repeat.termination.physical_termination
    or primary.cell_count != repeat.cell_count
    or primary.continued_cell_count != repeat.continued_cell_count
    or primary_measurement.handoff_links_verified is not True
    or repeat_measurement.handoff_links_verified is not True
  ):
    return False, None, None
  primary_signature = _research_chain_step_signature(primary)
  repeat_signature = _research_chain_step_signature(repeat)
  if primary_signature is None or repeat_signature is None:
    return False, None, None
  if len(primary_signature) != len(repeat_signature):
    return False, None, None
  for left, right in zip(primary_signature, repeat_signature, strict=True):
    if left[:-1] != right[:-1]:
      return False, None, None
  axial_residual = _maximum_sequence_residual(
    primary_metrics['axial_extents'],
    repeat_metrics['axial_extents'],
  )
  area_residual = _maximum_sequence_residual(
    primary_metrics['mesh_areas'],
    repeat_metrics['mesh_areas'],
  )
  if axial_residual is None or area_residual is None:
    return False, axial_residual, area_residual
  endpoint_ok = axial_residual <= position_tolerance_m
  area_ok = area_residual <= area_tolerance_m2
  step_endpoints_match = all(
    (
      left[-1] is None
      and right[-1] is None
    )
    or (
      left[-1] is not None
      and right[-1] is not None
      and abs(float(left[-1]) - float(right[-1])) <= position_tolerance_m
    )
    for left, right in zip(
      primary_signature,
      repeat_signature,
      strict=True,
    )
  )
  return endpoint_ok and area_ok and step_endpoints_match, axial_residual, area_residual
####


def measure_first_cell_geometry_owned_research_chain_refinement(
  cases: Sequence[MocFirstCellResearchChainRefinementCase],
  *,
  expected_sample_counts: Sequence[int] | None = None,
  expected_cell_count: int | None = None,
  endpoint_tolerance_m: float = 2.0e-2,
  shock_spacing_tolerance_m: float = 2.0e-2,
  maximum_radius_tolerance_m: float = 1.0e-2,
  mesh_area_tolerance_m2: float = 5.0e-2,
  deterministic_tolerance_m: float = 1.0e-12,
  deterministic_area_tolerance_m2: float = 1.0e-12,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-8,
) -> MocFirstCellResearchChainRefinementMeasurement:
  """Independently compare repeated multi-cell research-chain runs.

  The supplied planner results are already solved.  This operator never
  invokes a planner or solver; it reruns only the immutable measurement
  operators and compares the resulting chain geometry and recorded handoffs.
  A successful result therefore establishes deterministic local continuation
  and numerical sensitivity of the research lane, not canonical free-boundary
  closure.
  """

  for name, value in (
    ('endpoint_tolerance_m', endpoint_tolerance_m),
    ('shock_spacing_tolerance_m', shock_spacing_tolerance_m),
    ('maximum_radius_tolerance_m', maximum_radius_tolerance_m),
    ('mesh_area_tolerance_m2', mesh_area_tolerance_m2),
    ('deterministic_tolerance_m', deterministic_tolerance_m),
    ('deterministic_area_tolerance_m2', deterministic_area_tolerance_m2),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if expected_cell_count is not None and (
    isinstance(expected_cell_count, bool)
    or not isinstance(expected_cell_count, int)
    or expected_cell_count < 1
  ):
    raise ValueError('expected_cell_count must be positive when supplied')
  try:
    items = tuple(cases)
  except TypeError:
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
      expected_cell_count=expected_cell_count,
    )
  if len(items) < 2:
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.INVALID_INPUT,
      'at least two repeated chain refinement cases are required',
      cases=items,
      expected_cell_count=expected_cell_count,
    )
  if any(
    not isinstance(case, MocFirstCellResearchChainRefinementCase)
    for case in items
  ):
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain '
      'MocFirstCellResearchChainRefinementCase values',
      cases=items,
      expected_cell_count=expected_cell_count,
    )
  sample_counts = tuple(case.sample_count for case in items)
  sample_count_order_verified = all(
    right > left for left, right in zip(sample_counts, sample_counts[1:])
  )
  expected_counts = None
  if expected_sample_counts is not None:
    try:
      expected_counts = tuple(expected_sample_counts)
    except TypeError:
      return _first_cell_research_chain_refinement_failure(
        MocFirstCellResearchChainRefinementMeasurementStatus.INVALID_INPUT,
        'expected_sample_counts must be iterable',
        cases=items,
        expected_cell_count=expected_cell_count,
        sample_count_order_verified=sample_count_order_verified,
      )
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 3
      for value in expected_counts
    ):
      return _first_cell_research_chain_refinement_failure(
        MocFirstCellResearchChainRefinementMeasurementStatus.INVALID_INPUT,
        'expected_sample_counts must contain integers of at least three',
        cases=items,
        expected_cell_count=expected_cell_count,
        sample_count_order_verified=sample_count_order_verified,
      )
  expected_sample_counts_verified = bool(
    expected_counts is None or sample_counts == expected_counts
  )
  if not sample_count_order_verified or not expected_sample_counts_verified:
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'research-chain refinement sample counts must be strictly ordered and '
      'match the declared expectation',
      cases=items,
      expected_cell_count=expected_cell_count,
      sample_count_order_verified=sample_count_order_verified,
      expected_sample_counts_verified=expected_sample_counts_verified,
    )

  def measure_case(
    result: MocFirstCellResearchChainPlannerResult,
  ) -> MocFirstCellResearchChainMeasurement:
    return measure_first_cell_geometry_owned_research_chain(
      result.candidate,
      result.chain_planner,
      result.physical_fields,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      invariant_tolerance=invariant_tolerance,
    )

  measurements = tuple(measure_case(case.planner) for case in items)
  repeat_measurements = tuple(
    measure_case(case.repeat_planner) for case in items
  )
  if any(
    not measurement.converged or not repeat_measurement.converged
    for measurement, repeat_measurement in zip(
      measurements,
      repeat_measurements,
      strict=True,
    )
  ):
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.CASE_FAILURE,
      'one or more repeated research-chain cases failed independent measurement',
      cases=items,
      chain_measurements=measurements,
      repeat_chain_measurements=repeat_measurements,
      expected_cell_count=expected_cell_count,
      sample_count_order_verified=True,
      expected_sample_counts_verified=True,
    )

  primary_counts = tuple(measurement.field_count for measurement in measurements)
  repeat_counts = tuple(
    measurement.field_count for measurement in repeat_measurements
  )
  cell_count_consistent = bool(
    len(set((*primary_counts, *repeat_counts))) == 1
    and primary_counts[0] > 1
    and (
      expected_cell_count is None
      or primary_counts[0] == expected_cell_count
    )
  )
  planner_kinds = tuple(
    case.planner.planner_kind for case in items
  ) + tuple(
    case.repeat_planner.planner_kind for case in items
  )
  planner_kind_consistent = len(set(planner_kinds)) == 1
  termination_metadata = tuple(
    (
      result.termination.reason,
      result.termination.physical_termination,
    )
    for case in items
    for result in (case.planner, case.repeat_planner)
  )
  termination_consistency_verified = bool(
    len(set(termination_metadata)) == 1
    and termination_metadata[0][1] is False
  )
  metrics = tuple(
    _research_chain_geometry_metrics(measurement)
    for measurement in measurements
  )
  repeat_metrics = tuple(
    _research_chain_geometry_metrics(measurement)
    for measurement in repeat_measurements
  )
  if any(metric is None for metric in (*metrics, *repeat_metrics)):
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.CASE_FAILURE,
      'independent research-chain measurements did not expose complete '
      'finite geometry metrics',
      cases=items,
      chain_measurements=measurements,
      repeat_chain_measurements=repeat_measurements,
      expected_cell_count=expected_cell_count,
      cell_count=(primary_counts[0] if primary_counts else None),
      sample_count_order_verified=True,
      expected_sample_counts_verified=True,
      cell_count_consistent=cell_count_consistent,
      planner_kind_consistent=planner_kind_consistent,
      termination_consistency_verified=termination_consistency_verified,
    )
  resolved_metrics = tuple(metric for metric in metrics if metric is not None)
  resolved_repeat_metrics = tuple(
    metric for metric in repeat_metrics if metric is not None
  )
  geometry_shape_verified = bool(
    len({len(metric['axial_extents']) for metric in resolved_metrics}) == 1
    and len({len(metric['shock_spacing']) for metric in resolved_metrics}) == 1
    and len({len(metric['maximum_radii']) for metric in resolved_metrics}) == 1
    and len({len(metric['mesh_areas']) for metric in resolved_metrics}) == 1
    and all(
      len(metric['axial_extents']) == len(repeat_metric['axial_extents'])
      and len(metric['shock_spacing']) == len(repeat_metric['shock_spacing'])
      and len(metric['maximum_radii']) == len(repeat_metric['maximum_radii'])
      and len(metric['mesh_areas']) == len(repeat_metric['mesh_areas'])
      for metric, repeat_metric in zip(
        resolved_metrics,
        resolved_repeat_metrics,
        strict=True,
      )
    )
  )
  if not geometry_shape_verified:
    return _first_cell_research_chain_refinement_failure(
      MocFirstCellResearchChainRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'research-chain refinement cases must retain the same per-cell '
      'geometry shape',
      cases=items,
      chain_measurements=measurements,
      repeat_chain_measurements=repeat_measurements,
      expected_cell_count=expected_cell_count,
      cell_count=(primary_counts[0] if primary_counts else None),
      sample_count_order_verified=True,
      expected_sample_counts_verified=True,
      cell_count_consistent=cell_count_consistent,
      planner_kind_consistent=planner_kind_consistent,
      termination_consistency_verified=termination_consistency_verified,
      geometry_shape_verified=False,
    )

  deterministic_results = tuple(
    _research_chain_repeat_verified(
      case.planner,
      case.repeat_planner,
      measurement,
      repeat_measurement,
      position_tolerance_m=deterministic_tolerance_m,
      area_tolerance_m2=deterministic_area_tolerance_m2,
    )
    for case, measurement, repeat_measurement in zip(
      items,
      measurements,
      repeat_measurements,
      strict=True,
    )
  )
  deterministic_repeats_verified = all(item[0] for item in deterministic_results)
  repeat_axial_extent_residuals = tuple(
    item[1] for item in deterministic_results if item[1] is not None
  )
  repeat_mesh_area_residuals = tuple(
    item[2] for item in deterministic_results if item[2] is not None
  )

  def adjacent_residuals(key: str) -> tuple[float, ...]:
    return tuple(
      residual
      for left, right in zip(resolved_metrics, resolved_metrics[1:])
      for residual in (_maximum_sequence_residual(left[key], right[key]),)
      if residual is not None
    )

  axial_extent_residuals = adjacent_residuals('axial_extents')
  shock_spacing_residuals = adjacent_residuals('shock_spacing')
  maximum_radius_residuals = adjacent_residuals('maximum_radii')
  mesh_area_residuals = adjacent_residuals('mesh_areas')
  handoff_values = tuple(
    measurement.handoff_links_verified
    for measurement in (*measurements, *repeat_measurements)
  )
  handoff_links_verified = (
    True if all(value is True for value in handoff_values) else False
  )
  physical_closure_verified = bool(
    all(
      measurement.physical_closure_verified
      and repeat_measurement.physical_closure_verified
      for measurement, repeat_measurement in zip(
        measurements,
        repeat_measurements,
        strict=True,
      )
    )
  )
  fidelity_isolation_verified = bool(
    all(
      result.chain_promotion_blocked
      and result.production_claim_allowed is False
      and result.canonical_free_boundary_verified is False
      and result.canonical_euler_verified is False
      and result.external_validation_verified is False
      and measurement.fidelity_isolation_verified
      and repeat_measurement.fidelity_isolation_verified
      and measurement.chain_promotion_blocked
      and repeat_measurement.chain_promotion_blocked
      and measurement.production_claim_allowed is False
      and repeat_measurement.production_claim_allowed is False
      for case, measurement, repeat_measurement in zip(
        items,
        measurements,
        repeat_measurements,
        strict=True,
      )
      for result in (case.planner, case.repeat_planner)
    )
  )
  refinement_convergence_verified = bool(
    cell_count_consistent
    and planner_kind_consistent
    and termination_consistency_verified
    and deterministic_repeats_verified
    and len(repeat_axial_extent_residuals) == len(items)
    and len(repeat_mesh_area_residuals) == len(items)
    and all(
      residual <= float(endpoint_tolerance_m)
      for residual in axial_extent_residuals
    )
    and all(
      residual <= float(shock_spacing_tolerance_m)
      for residual in shock_spacing_residuals
    )
    and all(
      residual <= float(maximum_radius_tolerance_m)
      for residual in maximum_radius_residuals
    )
    and all(
      residual <= float(mesh_area_tolerance_m2)
      for residual in mesh_area_residuals
    )
    and all(
      residual <= float(deterministic_tolerance_m)
      for residual in repeat_axial_extent_residuals
    )
    and all(
      residual <= float(deterministic_area_tolerance_m2)
      for residual in repeat_mesh_area_residuals
    )
  )
  if (
    not cell_count_consistent
    or not planner_kind_consistent
    or not termination_consistency_verified
    or not geometry_shape_verified
  ):
    status = MocFirstCellResearchChainRefinementMeasurementStatus.CONSISTENCY_FAILURE
    message = (
      'repeated research-chain cases do not retain one cell count, planner '
      'kind, geometry shape, and typed termination outcome'
    )
  elif not physical_closure_verified or not fidelity_isolation_verified or not handoff_links_verified:
    status = MocFirstCellResearchChainRefinementMeasurementStatus.CONSISTENCY_FAILURE
    message = (
      'repeated research-chain cases failed independent handoff, physical '
      'closure, or fidelity-isolation checks'
    )
  elif not refinement_convergence_verified:
    status = MocFirstCellResearchChainRefinementMeasurementStatus.SENSITIVITY_FAILURE
    message = (
      'research-chain deterministic-repeat or resolution-sensitivity '
      'residuals exceeded their declared tolerances'
    )
  else:
    status = MocFirstCellResearchChainRefinementMeasurementStatus.CONVERGED
    message = (
      'independent repeated multi-cell research chains are deterministic and '
      'stable across the declared resolutions; canonical reflected '
      'free-boundary and product gates remain closed'
    )
  return _first_cell_research_chain_refinement_failure(
    status,
    message,
    cases=items,
    chain_measurements=measurements,
    repeat_chain_measurements=repeat_measurements,
    expected_cell_count=expected_cell_count,
    cell_count=primary_counts[0] if primary_counts else None,
    sample_count_order_verified=True,
    expected_sample_counts_verified=True,
    cell_count_consistent=cell_count_consistent,
    planner_kind_consistent=planner_kind_consistent,
    termination_consistency_verified=termination_consistency_verified,
    geometry_shape_verified=geometry_shape_verified,
    deterministic_repeats_verified=deterministic_repeats_verified,
    handoff_links_verified=handoff_links_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    axial_extent_residuals_m=axial_extent_residuals,
    shock_spacing_residuals_m=shock_spacing_residuals,
    maximum_radius_residuals_m=maximum_radius_residuals,
    mesh_area_residuals_m2=mesh_area_residuals,
    repeat_axial_extent_residuals_m=repeat_axial_extent_residuals,
    repeat_mesh_area_residuals_m2=repeat_mesh_area_residuals,
    refinement_convergence_verified=refinement_convergence_verified,
  )
####


class MocMixedRegimeEntropyTransportMeasurementStatus(str, Enum):
  """Outcome of independently measuring a mixed-regime entropy assignment."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'entropy-transport-request-failure'
  HANDOFF_FAILURE = 'entropy-transport-handoff-failure'
  FIELD_FAILURE = 'entropy-transport-field-failure'
  MAPPING_FAILURE = 'entropy-transport-mapping-failure'
  RESIDUAL_FAILURE = 'entropy-transport-residual-failure'
  CONSISTENCY_FAILURE = 'entropy-transport-consistency-failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeEntropyTransportMeasurement:
  """Independent evidence for an explicit entropy-to-field assignment.

  The operator receives the request, handoff, field, and transport result as
  separate values.  It recomputes the carried pressure profile and seam
  residuals locally; it never calls the transport solver or accepts its
  convenience flags as proof.
  """

  status: MocMixedRegimeEntropyTransportMeasurementStatus
  operator_id: str = MOC_MIXED_REGIME_ENTROPY_TRANSPORT_OPERATOR_ID
  transport: MocMixedRegimeEntropyTransportResult | None = None
  request_verified: bool = False
  handoff_verified: bool = False
  field_boundary_verified: bool = False
  source_profile_verified: bool = False
  streamline_assignment_verified: bool = False
  terminal_seam_verified: bool = False
  entropy_transport_verified: bool = False
  sample_count: int = 0
  streamline_count: int = 0
  terminal_node_index: int | None = None
  maximum_total_pressure_residual_Pa: float | None = None
  maximum_entropy_coordinate_residual: float | None = None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocMixedRegimeEntropyTransportMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocMixedRegimeEntropyTransportMeasurementStatus'
      )
    if self.transport is not None and not isinstance(
      self.transport,
      MocMixedRegimeEntropyTransportResult,
    ):
      raise TypeError(
        'transport must be a MocMixedRegimeEntropyTransportResult or None'
      )
    for name in ('sample_count', 'streamline_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.terminal_node_index is not None:
      if (
        isinstance(self.terminal_node_index, bool)
        or not isinstance(self.terminal_node_index, int)
        or self.terminal_node_index < 0
      ):
        raise ValueError(
          'terminal_node_index must be a nonnegative integer when supplied'
        )
    for name in (
      'maximum_total_pressure_residual_Pa',
      'maximum_entropy_coordinate_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    for name in (
      'request_verified',
      'handoff_verified',
      'field_boundary_verified',
      'source_profile_verified',
      'streamline_assignment_verified',
      'terminal_seam_verified',
      'entropy_transport_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeEntropyTransportMeasurementStatus.CONVERGED
  ####

  @property
  def transport_verified(self) -> bool:
    """Whether every independent assignment gate passed."""

    return bool(
      self.converged
      and self.request_verified
      and self.handoff_verified
      and self.field_boundary_verified
      and self.source_profile_verified
      and self.streamline_assignment_verified
      and self.terminal_seam_verified
      and self.entropy_transport_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'transport_verified': self.transport_verified,
      'request_verified': self.request_verified,
      'handoff_verified': self.handoff_verified,
      'field_boundary_verified': self.field_boundary_verified,
      'source_profile_verified': self.source_profile_verified,
      'streamline_assignment_verified': self.streamline_assignment_verified,
      'terminal_seam_verified': self.terminal_seam_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'sample_count': self.sample_count,
      'streamline_count': self.streamline_count,
      'terminal_node_index': self.terminal_node_index,
      'maximum_total_pressure_residual_Pa': (
        self.maximum_total_pressure_residual_Pa
      ),
      'maximum_entropy_coordinate_residual': (
        self.maximum_entropy_coordinate_residual
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####


def _entropy_transport_measurement_failure(
  status: MocMixedRegimeEntropyTransportMeasurementStatus,
  *,
  transport: MocMixedRegimeEntropyTransportResult | None = None,
  request_verified: bool = False,
  handoff_verified: bool = False,
  field_boundary_verified: bool = False,
  source_profile_verified: bool = False,
  streamline_assignment_verified: bool = False,
  terminal_seam_verified: bool = False,
  entropy_transport_verified: bool = False,
  sample_count: int = 0,
  streamline_count: int = 0,
  terminal_node_index: int | None = None,
  maximum_total_pressure_residual_Pa: float | None = None,
  maximum_entropy_coordinate_residual: float | None = None,
  message: str,
) -> MocMixedRegimeEntropyTransportMeasurement:
  return MocMixedRegimeEntropyTransportMeasurement(
    status=status,
    transport=transport,
    request_verified=request_verified,
    handoff_verified=handoff_verified,
    field_boundary_verified=field_boundary_verified,
    source_profile_verified=source_profile_verified,
    streamline_assignment_verified=streamline_assignment_verified,
    terminal_seam_verified=terminal_seam_verified,
    entropy_transport_verified=entropy_transport_verified,
    sample_count=sample_count,
    streamline_count=streamline_count,
    terminal_node_index=terminal_node_index,
    maximum_total_pressure_residual_Pa=maximum_total_pressure_residual_Pa,
    maximum_entropy_coordinate_residual=maximum_entropy_coordinate_residual,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def _interpolate_entropy_transport_pressure(
  handoff: MocMixedRegimeEntropyHandoffResult,
  coordinate: float,
) -> float:
  """Interpolate a verified handoff without using its convenience method."""

  if not isfinite(coordinate):
    raise ValueError('source arc coordinate must be finite')
  samples = handoff.samples
  arc = handoff.cumulative_arc_length_m
  if len(samples) < 2 or len(arc) != len(samples):
    raise ValueError('entropy handoff must expose a complete sample arc')
  if coordinate < arc[0] or coordinate > arc[-1]:
    raise ValueError('source arc coordinate lies outside the handoff arc')
  if coordinate <= arc[0]:
    return samples[0].downstream_total_pressure_Pa
  if coordinate >= arc[-1]:
    return samples[-1].downstream_total_pressure_Pa
  for first_arc, second_arc, first, second in zip(
    arc,
    arc[1:],
    samples,
    samples[1:],
    strict=True,
  ):
    if coordinate <= second_arc:
      fraction = (coordinate - first_arc) / (second_arc - first_arc)
      return (
        first.downstream_total_pressure_Pa
        + fraction * (
          second.downstream_total_pressure_Pa
          - first.downstream_total_pressure_Pa
        )
      )
  return samples[-1].downstream_total_pressure_Pa


def measure_mixed_regime_entropy_transport_boundary(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  field: MocMixedRegimeFieldResult,
  transport: MocMixedRegimeEntropyTransportResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  source_arc_length_tolerance_m: float = 1.0e-9,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeEntropyTransportMeasurement:
  """Remeasure an explicit mixed-regime entropy transport boundary."""

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if not isinstance(handoff, MocMixedRegimeEntropyHandoffResult):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.INVALID_INPUT,
      message='handoff must be a MocMixedRegimeEntropyHandoffResult',
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.INVALID_INPUT,
      message='field must be a MocMixedRegimeFieldResult',
    )
  if not isinstance(transport, MocMixedRegimeEntropyTransportResult):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.INVALID_INPUT,
      message='transport must be a MocMixedRegimeEntropyTransportResult',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('source_arc_length_tolerance_m', source_arc_length_tolerance_m),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  position_tolerance_m = float(position_tolerance_m)
  source_arc_length_tolerance_m = float(source_arc_length_tolerance_m)
  pressure_tolerance = float(pressure_tolerance)

  if transport.request != request:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.REQUEST_FAILURE,
      transport=transport,
      message='transport did not retain the exact mixed-regime request',
    )
  if transport.handoff != handoff:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.REQUEST_FAILURE,
      transport=transport,
      request_verified=True,
      message='transport did not retain the exact entropy handoff',
    )
  if transport.field != field:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.REQUEST_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      message='transport did not retain the exact mixed-regime field',
    )

  handoff_measurement = measure_mixed_regime_entropy_handoff(
    request,
    handoff,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
  )
  if not handoff_measurement.handoff_verified:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.HANDOFF_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=False,
      message=(
        'independent entropy-interface measurement failed before transport '
        f'could be checked: {handoff_measurement.message}'
      ),
    )

  boundary = field.boundary
  field_boundary_verified = bool(
    field.converged
    and boundary.converged
    and boundary.terminal == request.terminal
    and boundary.supersonic_patch == request.supersonic_patch
    and field.nodes
    and all(
      isinstance(sample, MocMixedRegimeFieldSample)
      and len(sample.point_m) == 2
      and all(isfinite(value) for value in sample.point_m)
      and 0.0 < sample.mach < 1.0
      and sample.static_pressure_Pa > 0.0
      and sample.total_pressure_Pa > 0.0
      and sample.gamma > 1.0
      for sample in field.nodes
    )
  )
  if not field_boundary_verified:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.FIELD_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      message=(
        'independent field seam checks require a converged scalar field with '
        'the exact terminal, patch, and finite subsonic nodes'
      ),
    )

  source_arc = transport.streamline_source_arc_length_m
  identifiers = transport.streamline_ids
  carried = transport.transported_total_pressure_Pa
  node_count = field.node_count
  if not (
    len(source_arc) == node_count
    and len(identifiers) == node_count
    and len(carried) == node_count
  ):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.MAPPING_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      sample_count=node_count,
      message=(
        'transport arrays must each contain exactly one entry per field node'
      ),
    )
  if any(
    not isfinite(coordinate) or coordinate < 0.0
    for coordinate in source_arc
  ) or any(
    isinstance(identifier, bool)
    or not isinstance(identifier, int)
    or identifier < 0
    for identifier in identifiers
  ) or any(
    not isfinite(pressure) or pressure <= 0.0
    for pressure in carried
  ):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.MAPPING_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      sample_count=node_count,
      streamline_count=len(set(identifiers)),
      message=(
        'transport arrays require finite nonnegative source coordinates, '
        'nonnegative integer streamline identifiers, and positive pressures'
      ),
    )

  arc = handoff.cumulative_arc_length_m
  if len(arc) < 2 or any(
    second <= first
    for first, second in zip(arc[:-1], arc[1:], strict=True)
  ):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.HANDOFF_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      sample_count=node_count,
      streamline_count=len(set(identifiers)),
      message='entropy handoff arc is not a strictly increasing interval',
    )
  if any(
    coordinate < arc[0] - source_arc_length_tolerance_m
    or coordinate > arc[-1] + source_arc_length_tolerance_m
    for coordinate in source_arc
  ):
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.MAPPING_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      source_profile_verified=False,
      sample_count=node_count,
      streamline_count=len(set(identifiers)),
      message='transport source coordinates require interpolation without extrapolation',
    )
  coordinate_groups: dict[int, list[float]] = {}
  for identifier, coordinate in zip(identifiers, source_arc, strict=True):
    coordinate_groups.setdefault(identifier, []).append(coordinate)
  streamline_assignment_verified = bool(
    coordinate_groups
    and all(
      len(coordinates) >= 2
      and max(coordinates) - min(coordinates)
      <= source_arc_length_tolerance_m
      for coordinates in coordinate_groups.values()
    )
  )
  if not streamline_assignment_verified:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.MAPPING_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      source_profile_verified=True,
      sample_count=node_count,
      streamline_count=len(coordinate_groups),
      message=(
        'each explicit streamline group must contain at least two nodes with '
        'one common source coordinate'
      ),
    )

  try:
    expected_carried = tuple(
      _interpolate_entropy_transport_pressure(handoff, coordinate)
      for coordinate in source_arc
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.HANDOFF_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      source_profile_verified=True,
      streamline_assignment_verified=True,
      sample_count=node_count,
      streamline_count=len(coordinate_groups),
      message=f'could not independently interpolate entropy source profile: {error}',
    )
  pressure_residuals = tuple(
    max(
      abs(sample.total_pressure_Pa - expected_pressure),
      abs(measured_pressure - expected_pressure),
    )
    for sample, measured_pressure, expected_pressure in zip(
      field.nodes,
      carried,
      expected_carried,
      strict=True,
    )
  )
  entropy_residuals = tuple(
    max(
      abs(log(expected_pressure / sample.total_pressure_Pa)),
      abs(log(expected_pressure / measured_pressure)),
    )
    for sample, measured_pressure, expected_pressure in zip(
      field.nodes,
      carried,
      expected_carried,
      strict=True,
    )
  )
  maximum_pressure_residual = max(pressure_residuals, default=None)
  maximum_entropy_residual = max(entropy_residuals, default=None)
  pressure_verified = all(
    residual <= pressure_tolerance * max(
      1.0,
      abs(sample.total_pressure_Pa),
      abs(measured_pressure),
      abs(expected_pressure),
    )
    for residual, sample, measured_pressure, expected_pressure in zip(
      pressure_residuals,
      field.nodes,
      carried,
      expected_carried,
      strict=True,
    )
  )
  terminal_indices = tuple(
    index
    for index, sample in enumerate(field.nodes)
    if hypot(
      sample.point_m[0] - request.terminal_point_m[0],
      sample.point_m[1] - request.terminal_point_m[1],
    ) <= position_tolerance_m
  )
  terminal_index = (
    transport.terminal_node_index
    if transport.terminal_node_index in terminal_indices
    and terminal_indices.count(transport.terminal_node_index) == 1
    else None
  )
  terminal_arc = (
    arc[handoff.terminal_sample_index]
    if handoff.terminal_sample_index is not None
    and 0 <= handoff.terminal_sample_index < len(arc)
    else None
  )
  terminal_seam_verified = bool(
    len(terminal_indices) == 1
    and terminal_index == terminal_indices[0]
    and terminal_arc is not None
    and abs(source_arc[terminal_index] - terminal_arc)
    <= source_arc_length_tolerance_m
    and _entropy_close(
      field.nodes[terminal_index].total_pressure_Pa,
      request.terminal_downstream_total_pressure_Pa,
      pressure_tolerance,
    )
    and _entropy_close(
      carried[terminal_index],
      request.terminal_downstream_total_pressure_Pa,
      pressure_tolerance,
    )
  )
  if not pressure_verified or not terminal_seam_verified:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.RESIDUAL_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      source_profile_verified=True,
      streamline_assignment_verified=True,
      terminal_seam_verified=terminal_seam_verified,
      entropy_transport_verified=False,
      sample_count=node_count,
      streamline_count=len(coordinate_groups),
      terminal_node_index=terminal_index,
      maximum_total_pressure_residual_Pa=maximum_pressure_residual,
      maximum_entropy_coordinate_residual=maximum_entropy_residual,
      message='independent entropy transport pressure or terminal seam residual failed',
    )

  metrics_verified = bool(
    transport.status is MocMixedRegimeEntropyTransportStatus.CONVERGED_REFERENCE
    and transport.model == 'solver-owned-mixed-regime-entropy-transport-boundary'
    and transport.field_boundary_verified
    and transport.source_profile_verified
    and transport.streamline_assignment_verified
    and transport.terminal_seam_verified
    and transport.entropy_transport_verified
    and transport.physical_closure_verified is False
    and transport.canonical_free_boundary_verified is False
    and transport.chain_promotion_blocked
    and transport.production_claim_allowed is False
    and transport.terminal_node_index == terminal_index
    and transport.streamline_count == len(coordinate_groups)
    and transport.node_count == node_count
    and transport.maximum_total_pressure_residual_Pa is not None
    and transport.maximum_entropy_coordinate_residual is not None
    and _entropy_close(
      transport.maximum_total_pressure_residual_Pa,
      maximum_pressure_residual,
      pressure_tolerance,
    )
    and _entropy_close(
      transport.maximum_entropy_coordinate_residual,
      maximum_entropy_residual,
      pressure_tolerance,
    )
  )
  if not metrics_verified:
    return _entropy_transport_measurement_failure(
      MocMixedRegimeEntropyTransportMeasurementStatus.CONSISTENCY_FAILURE,
      transport=transport,
      request_verified=True,
      handoff_verified=True,
      field_boundary_verified=True,
      source_profile_verified=True,
      streamline_assignment_verified=True,
      terminal_seam_verified=True,
      sample_count=node_count,
      streamline_count=len(coordinate_groups),
      terminal_node_index=terminal_index,
      maximum_total_pressure_residual_Pa=maximum_pressure_residual,
      maximum_entropy_coordinate_residual=maximum_entropy_residual,
      message='transport result flags or reported residuals failed independent consistency checks',
    )
  return MocMixedRegimeEntropyTransportMeasurement(
    status=MocMixedRegimeEntropyTransportMeasurementStatus.CONVERGED,
    transport=transport,
    request_verified=True,
    handoff_verified=True,
    field_boundary_verified=True,
    source_profile_verified=True,
    streamline_assignment_verified=True,
    terminal_seam_verified=True,
    entropy_transport_verified=True,
    sample_count=node_count,
    streamline_count=len(coordinate_groups),
    terminal_node_index=terminal_index,
    maximum_total_pressure_residual_Pa=maximum_pressure_residual,
    maximum_entropy_coordinate_residual=maximum_entropy_residual,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent measurement reproduced the explicit entropy source map, '
      'scalar field pressure lineage, and terminal seam; coupled Euler/free-'
      'boundary closure remains separate'
    ),
  )
####


class MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus(str, Enum):
  """Outcome of independently measuring the variable-entropy reference."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'variable-entropy-request-failure'
  HANDOFF_FAILURE = 'variable-entropy-handoff-failure'
  CONTROL_SECTION_FAILURE = 'variable-entropy-control-section-failure'
  GEOMETRY_FAILURE = 'variable-entropy-geometry-failure'
  FIELD_FAILURE = 'variable-entropy-field-failure'
  TOPOLOGY_FAILURE = 'variable-entropy-topology-failure'
  MAPPING_FAILURE = 'variable-entropy-source-mapping-failure'
  CONDITION_FAILURE = 'variable-entropy-condition-failure'
  RESIDUAL_FAILURE = 'variable-entropy-residual-failure'
  CONSISTENCY_FAILURE = 'variable-entropy-consistency-failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeVariableEntropyFreeBoundaryMeasurement:
  """Independent evidence for the solver-owned variable-entropy reference.

  The operator treats the solver result as data.  It reconstructs the reverse
  entropy map, structured stream-tube node layout, closed mesh perimeter,
  ambient/tangency condition, and reported local residuals.  It never calls
  the variable-entropy solver and never converts this reference into a
  canonical Euler or continued-chain acceptance.
  """

  status: MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus
  operator_id: str = MOC_MIXED_REGIME_VARIABLE_ENTROPY_FREE_BOUNDARY_OPERATOR_ID
  reference: MocMixedRegimeVariableEntropyFreeBoundaryResult | None = None
  request_verified: bool = False
  handoff_verified: bool = False
  control_section_verified: bool = False
  source_streamline_mapping_verified: bool = False
  field_boundary_verified: bool = False
  downstream_condition_verified: bool = False
  field_topology_verified: bool = False
  continuity_verified: bool = False
  entropy_transport_verified: bool = False
  free_boundary_condition_verified: bool = False
  reported_flags_verified: bool = False
  reference_model_verified: bool = False
  physical_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  node_count: int = 0
  cell_count: int = 0
  axial_station_count: int = 0
  transverse_station_count: int = 0
  streamline_count: int = 0
  maximum_source_arc_residual_m: float | None = None
  maximum_source_pressure_residual_Pa: float | None = None
  maximum_source_gamma_residual: float | None = None
  maximum_continuity_residual: float | None = None
  maximum_connector_continuity_residual: float | None = None
  maximum_entrance_continuity_residual: float | None = None
  maximum_entropy_advection_residual: float | None = None
  maximum_entrance_entropy_advection_residual: float | None = None
  maximum_transverse_momentum_residual: float | None = None
  maximum_mass_flow_residual: float | None = None
  maximum_entrance_mass_flow_residual: float | None = None
  maximum_free_boundary_pressure_residual_Pa: float | None = None
  maximum_free_boundary_tangent_residual_rad: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus'
      )
    if self.reference is not None and not isinstance(
      self.reference,
      MocMixedRegimeVariableEntropyFreeBoundaryResult,
    ):
      raise TypeError(
        'reference must be a '
        'MocMixedRegimeVariableEntropyFreeBoundaryResult or None'
      )
    for name in (
      'node_count',
      'cell_count',
      'axial_station_count',
      'transverse_station_count',
      'streamline_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in (
      'maximum_source_arc_residual_m',
      'maximum_source_pressure_residual_Pa',
      'maximum_source_gamma_residual',
      'maximum_continuity_residual',
      'maximum_connector_continuity_residual',
      'maximum_entrance_continuity_residual',
      'maximum_entropy_advection_residual',
      'maximum_entrance_entropy_advection_residual',
      'maximum_transverse_momentum_residual',
      'maximum_mass_flow_residual',
      'maximum_entrance_mass_flow_residual',
      'maximum_free_boundary_pressure_residual_Pa',
      'maximum_free_boundary_tangent_residual_rad',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        object.__setattr__(self, name, numeric)
    for name in (
      'request_verified',
      'handoff_verified',
      'control_section_verified',
      'source_streamline_mapping_verified',
      'field_boundary_verified',
      'downstream_condition_verified',
      'field_topology_verified',
      'continuity_verified',
      'entropy_transport_verified',
      'free_boundary_condition_verified',
      'reported_flags_verified',
      'reference_model_verified',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONVERGED
    )
  ####

  @property
  def reference_verified(self) -> bool:
    """Whether all independent local gates passed."""

    return bool(
      self.converged
      and self.request_verified
      and self.handoff_verified
      and self.control_section_verified
      and self.source_streamline_mapping_verified
      and self.field_boundary_verified
      and self.downstream_condition_verified
      and self.field_topology_verified
      and self.continuity_verified
      and self.entropy_transport_verified
      and self.free_boundary_condition_verified
      and self.reported_flags_verified
      and self.reference_model_verified
      and self.physical_closure_verified is False
      and self.canonical_free_boundary_verified is False
      and self.canonical_euler_verified is False
      and self.chain_promotion_blocked
      and self.production_claim_allowed is False
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'reference_verified': self.reference_verified,
      'request_verified': self.request_verified,
      'handoff_verified': self.handoff_verified,
      'control_section_verified': self.control_section_verified,
      'source_streamline_mapping_verified': self.source_streamline_mapping_verified,
      'field_boundary_verified': self.field_boundary_verified,
      'downstream_condition_verified': self.downstream_condition_verified,
      'field_topology_verified': self.field_topology_verified,
      'continuity_verified': self.continuity_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'free_boundary_condition_verified': self.free_boundary_condition_verified,
      'reported_flags_verified': self.reported_flags_verified,
      'reference_model_verified': self.reference_model_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'counts': {
        'node_count': self.node_count,
        'cell_count': self.cell_count,
        'axial_station_count': self.axial_station_count,
        'transverse_station_count': self.transverse_station_count,
        'streamline_count': self.streamline_count,
      },
      'source_residuals': {
        'maximum_source_arc_residual_m': self.maximum_source_arc_residual_m,
        'maximum_source_pressure_residual_Pa': (
          self.maximum_source_pressure_residual_Pa
        ),
        'maximum_source_gamma_residual': self.maximum_source_gamma_residual,
      },
      'field_residuals': {
        'maximum_continuity_residual': self.maximum_continuity_residual,
        'maximum_connector_continuity_residual': (
          self.maximum_connector_continuity_residual
        ),
        'maximum_entrance_continuity_residual': (
          self.maximum_entrance_continuity_residual
        ),
        'maximum_entropy_advection_residual': (
          self.maximum_entropy_advection_residual
        ),
        'maximum_entrance_entropy_advection_residual': (
          self.maximum_entrance_entropy_advection_residual
        ),
        'maximum_transverse_momentum_residual': (
          self.maximum_transverse_momentum_residual
        ),
        'maximum_mass_flow_residual': self.maximum_mass_flow_residual,
        'maximum_entrance_mass_flow_residual': (
          self.maximum_entrance_mass_flow_residual
        ),
        'maximum_free_boundary_pressure_residual_Pa': (
          self.maximum_free_boundary_pressure_residual_Pa
        ),
        'maximum_free_boundary_tangent_residual_rad': (
          self.maximum_free_boundary_tangent_residual_rad
        ),
      },
      'reference': None if self.reference is None else self.reference.as_report(),
      'claim_status': (
        'independent-variable-entropy-free-boundary-reference-measurement; '
        'mapped-continuity-and-entropy-evidence-only; canonical-2d-euler-'
        'free-boundary-and-external-validation-pending'
      ),
      'message': self.message,
    }
  ####


def _variable_entropy_measurement_failure(
  status: MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus,
  *,
  reference: MocMixedRegimeVariableEntropyFreeBoundaryResult | None = None,
  message: str,
  **kwargs: object,
) -> MocMixedRegimeVariableEntropyFreeBoundaryMeasurement:
  return MocMixedRegimeVariableEntropyFreeBoundaryMeasurement(
    status=status,
    reference=reference,
    physical_closure_verified=False,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
    **kwargs,
  )
####


def _variable_entropy_profile_value(
  handoff: MocMixedRegimeEntropyHandoffResult,
  coordinate: float,
  attribute: str,
) -> float:
  """Interpolate a handoff attribute without using the solver helper."""

  arc = handoff.cumulative_arc_length_m
  samples = handoff.samples
  if len(arc) != len(samples) or len(samples) < 2:
    raise ValueError('entropy handoff must expose a complete ordered profile')
  if coordinate < arc[0] or coordinate > arc[-1]:
    raise ValueError('source coordinate lies outside the handoff profile')
  if coordinate <= arc[0]:
    return float(getattr(samples[0], attribute))
  if coordinate >= arc[-1]:
    return float(getattr(samples[-1], attribute))
  for first_arc, second_arc, first, second in zip(
    arc,
    arc[1:],
    samples,
    samples[1:],
    strict=True,
  ):
    if coordinate <= second_arc:
      fraction = (coordinate - first_arc) / (second_arc - first_arc)
      first_value = float(getattr(first, attribute))
      second_value = float(getattr(second, attribute))
      return first_value + fraction * (second_value - first_value)
  return float(getattr(samples[-1], attribute))
####


def _variable_entropy_triangle_gradients(
  points: Sequence[Point],
  values: Sequence[float],
) -> tuple[float, float, float]:
  if len(points) != 3 or len(values) != 3:
    raise ValueError('variable-entropy residuals require triangular cells')
  (x1, y1), (x2, y2), (x3, y3) = points
  denominator = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(denominator) or abs(denominator) <= 1.0e-20:
    raise ValueError('variable-entropy residual cell has zero area')
  gradient_x = (
    values[0] * (y2 - y3)
    + values[1] * (y3 - y1)
    + values[2] * (y1 - y2)
  ) / denominator
  gradient_y = (
    values[0] * (x3 - x2)
    + values[1] * (x1 - x3)
    + values[2] * (x2 - x1)
  ) / denominator
  diameter = max(
    hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]),
    hypot(points[2][0] - points[1][0], points[2][1] - points[1][1]),
    hypot(points[0][0] - points[2][0], points[0][1] - points[2][1]),
  )
  return gradient_x, gradient_y, diameter
####


def _variable_entropy_mass_flux_factor(mach: float, gamma: float) -> float:
  return mach * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (-(gamma + 1.0) / (2.0 * (gamma - 1.0)))
####


def _variable_entropy_normalized_density(
  total_pressure_Pa: float,
  reference_total_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  enthalpy_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  return (
    total_pressure_Pa / reference_total_pressure_Pa
  ) ** (1.0 / gamma) * enthalpy_factor ** (-1.0 / (gamma - 1.0))
####


def _variable_entropy_metric_close(
  first: float | None,
  second: float | None,
  tolerance: float,
) -> bool:
  return bool(
    first is not None
    and second is not None
    and abs(float(first) - float(second))
    <= tolerance * max(1.0, abs(float(first)), abs(float(second)))
  )
####


def measure_mixed_regime_variable_entropy_free_boundary(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  control_section: MocMixedRegimeControlSection,
  reference: MocMixedRegimeVariableEntropyFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  residual_tolerance: float = 1.0e-7,
  continuity_tolerance: float = 0.25,
  entropy_transport_tolerance: float = 0.25,
) -> MocMixedRegimeVariableEntropyFreeBoundaryMeasurement:
  """Independently remeasure the solver-owned variable-entropy reference."""

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if not isinstance(handoff, MocMixedRegimeEntropyHandoffResult):
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message='handoff must be a MocMixedRegimeEntropyHandoffResult',
    )
  if not isinstance(control_section, MocMixedRegimeControlSection):
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message='control_section must be a MocMixedRegimeControlSection',
    )
  if not isinstance(
    reference,
    MocMixedRegimeVariableEntropyFreeBoundaryResult,
  ):
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message=(
        'reference must be a '
        'MocMixedRegimeVariableEntropyFreeBoundaryResult'
      ),
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('residual_tolerance', residual_tolerance),
    ('continuity_tolerance', continuity_tolerance),
    ('entropy_transport_tolerance', entropy_transport_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  position_tolerance_m = float(position_tolerance_m)
  state_tolerance = float(state_tolerance)
  pressure_tolerance = float(pressure_tolerance)
  tangent_tolerance_rad = float(tangent_tolerance_rad)
  residual_tolerance = float(residual_tolerance)
  continuity_tolerance = float(continuity_tolerance)
  entropy_transport_tolerance = float(entropy_transport_tolerance)

  request_verified = reference.request == request
  if not request_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.REQUEST_FAILURE,
      reference=reference,
      message='reference did not retain the exact mixed-regime request',
    )
  handoff_verified = reference.handoff == handoff
  if not handoff_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.REQUEST_FAILURE,
      reference=reference,
      request_verified=True,
      message='reference did not retain the exact entropy handoff',
    )
  control_identity_verified = reference.control_section == control_section
  if not control_identity_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.REQUEST_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      message='reference did not retain the exact control section',
    )

  handoff_measurement = measure_mixed_regime_entropy_handoff(
    request,
    handoff,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
  )
  if not handoff_measurement.handoff_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.HANDOFF_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=False,
      message=(
        'independent entropy handoff measurement failed before the field '
        f'audit: {handoff_measurement.message}'
      ),
    )

  control_measurement = measure_mixed_regime_control_section(
    request,
    control_section,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
  )
  control_section_verified = bool(
    control_measurement.converged
    and reference.control_section_validation is not None
    and reference.control_section_validation.converged
    and reference.control_section_validation.request == request
    and reference.control_section_validation.section == control_section
  )
  if not control_section_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONTROL_SECTION_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      message=(
        'independent control-section measurement failed: '
        f'{control_measurement.message}'
      ),
    )

  try:
    terminal_x, terminal_y = request.terminal_point_m
    section_x = control_section.points_m[0][0]
    inlet_height = control_section.points_m[-1][1] - control_section.points_m[0][1]
    fractions = tuple(
      (point[1] - terminal_y) / inlet_height
      for point in control_section.points_m
    )
    interface_length = handoff.cumulative_arc_length_m[-1]
    source_arc_by_fraction = tuple(
      interface_length * (1.0 - fraction) for fraction in fractions
    )
    source_pressure_by_fraction = tuple(
      _variable_entropy_profile_value(
        handoff,
        coordinate,
        'downstream_total_pressure_Pa',
      )
      for coordinate in source_arc_by_fraction
    )
    source_gamma_by_fraction = tuple(
      _variable_entropy_profile_value(handoff, coordinate, 'gamma')
      for coordinate in source_arc_by_fraction
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      message=f'could not reconstruct control-section source geometry: {error}',
    )
  if len(fractions) < 3 or inlet_height <= position_tolerance_m:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      message='reference measurement requires at least three positive streamlines',
    )

  axial_count = reference.axial_station_count
  transverse_count = reference.transverse_station_count
  expected_node_count = 1 + axial_count * transverse_count
  expected_cell_count = (
    transverse_count - 1
    + 2 * (axial_count - 1) * (transverse_count - 1)
  )
  if (
    axial_count < 5
    or transverse_count != len(fractions)
    or reference.node_count != expected_node_count
    or reference.cell_count != expected_cell_count
  ):
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      node_count=0 if reference.field is None else reference.field.node_count,
      cell_count=0 if reference.field is None else reference.field.cell_count,
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      message='reference node/cell counts do not match its declared structured mesh',
    )

  field = reference.field
  boundary = reference.boundary
  condition = reference.downstream_condition
  if field is None or boundary is None or condition is None:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      message='reference must retain its field, scalar boundary, and downstream condition',
    )

  def grid_index(station: int, transverse: int) -> int:
    return 1 + station * transverse_count + transverse

  expected_initial_heights = tuple(
    inlet_height
    + (reference.initial_outlet_height_m - inlet_height)
    * station
    / (axial_count - 1)
    for station in range(axial_count)
  )
  expected_heights = tuple(
    reference.field.nodes[grid_index(station, transverse_count - 1)].point_m[1]
    - terminal_y
    for station in range(axial_count)
  )
  expected_free_boundary_points = tuple(
    reference.field.nodes[grid_index(station, transverse_count - 1)].point_m
    for station in range(axial_count)
  )
  initial_geometry_verified = bool(
    len(reference.initial_free_boundary_heights_m) == axial_count
    and all(
      _variable_entropy_metric_close(
        value,
        expected,
        residual_tolerance,
      )
      for value, expected in zip(
        reference.initial_free_boundary_heights_m,
        expected_initial_heights,
        strict=True,
      )
    )
  )
  free_boundary_geometry_verified = bool(
    len(reference.free_boundary_heights_m) == axial_count
    and len(reference.free_boundary_points_m) == axial_count
    and all(
      _variable_entropy_metric_close(value, expected, residual_tolerance)
      for value, expected in zip(
        reference.free_boundary_heights_m,
        expected_heights,
        strict=True,
      )
    )
    and all(
      hypot(point[0] - expected[0], point[1] - expected[1])
      <= position_tolerance_m
      for point, expected in zip(
        reference.free_boundary_points_m,
        expected_free_boundary_points,
        strict=True,
      )
    )
    and reference.outlet_height_m is not None
    and _variable_entropy_metric_close(
      reference.outlet_height_m,
      expected_heights[-1],
      residual_tolerance,
    )
  )
  if not initial_geometry_verified or not free_boundary_geometry_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      message='reported free-boundary geometry does not reproduce the structured map',
    )

  expected_streamline_ids = (0, *(
    transverse
    for _station in range(axial_count)
    for transverse in range(transverse_count)
  ))
  expected_node_arc = (
    interface_length,
    *(
      source_arc_by_fraction[transverse]
      for _station in range(axial_count)
      for transverse in range(transverse_count)
    ),
  )
  expected_node_pressure = (
    request.terminal_downstream_total_pressure_Pa,
    *(
      source_pressure_by_fraction[transverse]
      for _station in range(axial_count)
      for transverse in range(transverse_count)
    ),
  )
  expected_node_gamma = (
    request.terminal.upstream_state.gamma,
    *(
      source_gamma_by_fraction[transverse]
      for _station in range(axial_count)
      for transverse in range(transverse_count)
    ),
  )
  field_nodes = field.nodes
  node_geometry_verified = True
  node_state_verified = True
  node_arc_residuals: list[float] = []
  node_pressure_residuals: list[float] = []
  node_gamma_residuals: list[float] = []
  for node_index, (sample, expected_arc, expected_pressure, expected_gamma) in enumerate(
    zip(
      field_nodes,
      expected_node_arc,
      expected_node_pressure,
      expected_node_gamma,
      strict=True,
    )
  ):
    if node_index == 0:
      expected_point = request.terminal_point_m
    else:
      relative = node_index - 1
      station = relative // transverse_count
      transverse = relative % transverse_count
      dx = reference.downstream_length_m / (axial_count - 1)
      expected_point = (
        section_x + station * dx,
        terminal_y + fractions[transverse] * expected_heights[station],
      )
    node_geometry_verified = bool(
      node_geometry_verified
      and hypot(
        sample.point_m[0] - expected_point[0],
        sample.point_m[1] - expected_point[1],
      ) <= position_tolerance_m
    )
    node_state_verified = bool(
      node_state_verified
      and 0.0 < sample.mach < 1.0
      and sample.static_pressure_Pa > 0.0
      and sample.total_pressure_Pa > 0.0
      and sample.gamma > 1.0
    )
    node_arc_residuals.append(
      abs(reference.source_arc_length_m[node_index] - expected_arc)
      if node_index < len(reference.source_arc_length_m)
      else float('inf')
    )
    node_pressure_residuals.append(
      max(
        abs(sample.total_pressure_Pa - expected_pressure),
        abs(reference.transported_total_pressure_Pa[node_index] - expected_pressure)
        if node_index < len(reference.transported_total_pressure_Pa)
        else float('inf'),
      )
    )
    node_gamma_residuals.append(abs(sample.gamma - expected_gamma))
  source_arrays_verified = bool(
    len(reference.source_arc_length_m) == expected_node_count
    and len(reference.streamline_ids) == expected_node_count
    and len(reference.transported_total_pressure_Pa) == expected_node_count
    and tuple(reference.streamline_ids) == expected_streamline_ids
    and len(reference.transverse_fractions) == transverse_count
    and all(
      _variable_entropy_metric_close(value, expected, residual_tolerance)
      for value, expected in zip(
        reference.transverse_fractions,
        fractions,
        strict=True,
      )
    )
    and len(reference.source_arc_length_by_transverse_index_m) == transverse_count
    and len(reference.source_total_pressure_by_transverse_index_Pa) == transverse_count
    and len(reference.source_gamma_by_transverse_index) == transverse_count
    and all(
      _variable_entropy_metric_close(value, expected, residual_tolerance)
      for value, expected in zip(
        reference.source_arc_length_by_transverse_index_m,
        source_arc_by_fraction,
        strict=True,
      )
    )
    and all(
      _variable_entropy_metric_close(value, expected, residual_tolerance)
      for value, expected in zip(
        reference.source_total_pressure_by_transverse_index_Pa,
        source_pressure_by_fraction,
        strict=True,
      )
    )
    and all(
      _variable_entropy_metric_close(value, expected, residual_tolerance)
      for value, expected in zip(
        reference.source_gamma_by_transverse_index,
        source_gamma_by_fraction,
        strict=True,
      )
    )
  )
  maximum_source_arc_residual = max(node_arc_residuals, default=None)
  maximum_source_pressure_residual = max(node_pressure_residuals, default=None)
  maximum_source_gamma_residual = max(node_gamma_residuals, default=None)
  source_streamline_mapping_verified = bool(
    source_arrays_verified
    and node_geometry_verified
    and node_state_verified
    and maximum_source_arc_residual is not None
    and maximum_source_arc_residual <= residual_tolerance
    and maximum_source_pressure_residual is not None
    and maximum_source_pressure_residual
    <= pressure_tolerance * max(
      1.0,
      abs(request.terminal_downstream_total_pressure_Pa),
      max(source_pressure_by_fraction, default=1.0),
    )
    and maximum_source_gamma_residual is not None
    and maximum_source_gamma_residual <= state_tolerance
  )
  if not source_streamline_mapping_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.MAPPING_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      node_count=len(field_nodes),
      cell_count=len(field.cells),
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      streamline_count=len(set(reference.streamline_ids)),
      maximum_source_arc_residual_m=maximum_source_arc_residual,
      maximum_source_pressure_residual_Pa=maximum_source_pressure_residual,
      maximum_source_gamma_residual=maximum_source_gamma_residual,
      message='independent reverse entropy and streamline mapping audit failed',
    )

  perimeter_indices = [0, grid_index(0, transverse_count - 1)]
  perimeter_indices.extend(
    grid_index(station, transverse_count - 1)
    for station in range(1, axial_count)
  )
  perimeter_indices.extend(
    grid_index(axial_count - 1, transverse)
    for transverse in range(transverse_count - 2, -1, -1)
  )
  perimeter_indices.extend(
    grid_index(station, 0)
    for station in range(axial_count - 2, -1, -1)
  )
  perimeter_indices.append(0)
  expected_perimeter_points = tuple(
    field_nodes[index].point_m for index in perimeter_indices
  )
  expected_perimeter_samples = tuple(field_nodes[index] for index in perimeter_indices)
  perimeter_layout_verified = bool(
    boundary.perimeter_points_m == expected_perimeter_points
    and boundary.subsonic_samples == expected_perimeter_samples
    and field.boundary == boundary
  )
  rechecked_boundary = validate_mixed_regime_boundary(
    request.terminal,
    request.supersonic_patch,
    supersonic_patch_converged=True,
    subsonic_samples=expected_perimeter_samples,
    perimeter_points_m=expected_perimeter_points,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
  )
  field_boundary_verified = bool(
    perimeter_layout_verified
    and rechecked_boundary.converged
    and boundary.converged
    and boundary.terminal == request.terminal
    and boundary.supersonic_patch == request.supersonic_patch
    and field.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD
    and field.model == reference.model
    and field.downstream_condition is None
  )
  if not field_boundary_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      source_streamline_mapping_verified=True,
      node_count=len(field_nodes),
      cell_count=len(field.cells),
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      streamline_count=transverse_count,
      maximum_source_arc_residual_m=maximum_source_arc_residual,
      maximum_source_pressure_residual_Pa=maximum_source_pressure_residual,
      maximum_source_gamma_residual=maximum_source_gamma_residual,
      message='independent scalar perimeter or field seam audit failed',
    )

  expected_condition_edges = tuple(range(4, axial_count))
  expected_condition_samples = tuple(range(4, axial_count + 1))
  rechecked_condition = validate_mixed_regime_downstream_condition(
    rechecked_boundary,
    MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
    ambient_pressure_Pa=reference.ambient_pressure_Pa,
    condition_edge_indices=expected_condition_edges,
    condition_sample_indices=expected_condition_samples,
    position_tolerance_m=position_tolerance_m,
    tangent_tolerance_rad=tangent_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
  )
  downstream_condition_verified = bool(
    rechecked_condition.converged
    and condition.boundary == boundary
    and condition.condition_kind
    is MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY
    and condition.condition_edge_indices == expected_condition_edges
    and condition.condition_sample_indices == expected_condition_samples
  )
  if not downstream_condition_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      source_streamline_mapping_verified=True,
      field_boundary_verified=True,
      node_count=len(field_nodes),
      cell_count=len(field.cells),
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      streamline_count=transverse_count,
      maximum_source_arc_residual_m=maximum_source_arc_residual,
      maximum_source_pressure_residual_Pa=maximum_source_pressure_residual,
      maximum_source_gamma_residual=maximum_source_gamma_residual,
      maximum_free_boundary_pressure_residual_Pa=(
        rechecked_condition.maximum_pressure_residual_Pa
      ),
      maximum_free_boundary_tangent_residual_rad=(
        rechecked_condition.maximum_tangent_residual_rad
      ),
      message='independent ambient free-boundary condition audit failed',
    )

  topology = validate_moc_mesh(field.cells)
  field_topology_verified = bool(
    topology == field.topology
    and topology.forms_closed_zone
    and not topology.nonmanifold_edge_count
  )
  if not field_topology_verified:
    return _variable_entropy_measurement_failure(
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.TOPOLOGY_FAILURE,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      source_streamline_mapping_verified=True,
      field_boundary_verified=True,
      downstream_condition_verified=True,
      node_count=len(field_nodes),
      cell_count=len(field.cells),
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      streamline_count=transverse_count,
      message=f'independent variable-entropy mesh topology failed: {topology.message}',
    )

  node_indices_by_point = {sample.point_m: index for index, sample in enumerate(field_nodes)}
  connector_continuity: list[float] = []
  entrance_continuity: list[float] = []
  continuity: list[float] = []
  entrance_entropy: list[float] = []
  entropy: list[float] = []
  transverse_momentum: list[float] = []
  cell_layout_verified = True
  reference_total_pressure = request.terminal_downstream_total_pressure_Pa
  for cell in field.cells:
    if not isinstance(cell, MocCharacteristicCell) or len(cell.vertices_xr_m) != 3:
      cell_layout_verified = False
      continue
    try:
      indices = tuple(node_indices_by_point[point] for point in cell.vertices_xr_m)
    except KeyError:
      cell_layout_verified = False
      continue
    samples = tuple(field_nodes[index] for index in indices)
    points = tuple(sample.point_m for sample in samples)
    densities = tuple(
      _variable_entropy_normalized_density(
        sample.total_pressure_Pa,
        reference_total_pressure,
        sample.mach,
        sample.gamma,
      )
      for sample in samples
    )
    speeds = tuple(
      sample.mach
      / sqrt(1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach * sample.mach)
      for sample in samples
    )
    velocity = tuple(
      (speed * cos(sample.flow_angle_rad), speed * sin(sample.flow_angle_rad))
      for speed, sample in zip(speeds, samples, strict=True)
    )
    mass_velocity = tuple(
      (density * vector[0], density * vector[1])
      for density, vector in zip(densities, velocity, strict=True)
    )
    mass_x_x, _mass_x_y, diameter = _variable_entropy_triangle_gradients(
      points,
      tuple(vector[0] for vector in mass_velocity),
    )
    _mass_y_x, mass_y_y, _ = _variable_entropy_triangle_gradients(
      points,
      tuple(vector[1] for vector in mass_velocity),
    )
    continuity_residual = abs(mass_x_x + mass_y_y) * diameter / max(
      1.0e-12,
      max(hypot(*vector) for vector in mass_velocity),
    )
    entropy_x, entropy_y, _ = _variable_entropy_triangle_gradients(
      points,
      tuple(log(sample.total_pressure_Pa) for sample in samples),
    )
    center_velocity = (
      sum(vector[0] for vector in velocity) / 3.0,
      sum(vector[1] for vector in velocity) / 3.0,
    )
    entropy_residual = abs(
      center_velocity[0] * entropy_x + center_velocity[1] * entropy_y
    ) * diameter / max(1.0e-12, hypot(*center_velocity))
    _pressure_x, pressure_y, _ = _variable_entropy_triangle_gradients(
      points,
      tuple(sample.static_pressure_Pa / reference_total_pressure for sample in samples),
    )
    velocity_y_x, velocity_y_y, _ = _variable_entropy_triangle_gradients(
      points,
      tuple(vector[1] for vector in velocity),
    )
    transverse_residual = abs(
      center_velocity[0] * velocity_y_x
      + center_velocity[1] * velocity_y_y
      + pressure_y / max(1.0e-12, sum(densities) / 3.0)
    ) * diameter
    is_connector = cell.cell_kind == 'variable-entropy-terminal-connector'
    is_streamtube = cell.cell_kind == 'variable-entropy-streamtube'
    station_index = (
      cell.boundary_indices[0]
      if is_streamtube and cell.boundary_indices
      else -1
    )
    is_entrance = is_connector or station_index < 3
    cell_layout_verified = bool(cell_layout_verified and (is_connector or is_streamtube))
    if is_connector:
      connector_continuity.append(continuity_residual)
    elif is_entrance:
      entrance_continuity.append(continuity_residual)
    else:
      continuity.append(continuity_residual)
    if is_entrance:
      entrance_entropy.append(entropy_residual)
    else:
      entropy.append(entropy_residual)
    transverse_momentum.append(transverse_residual)

  mass_flow: list[float] = []
  entrance_mass_flow: list[float] = []
  for station in range(axial_count):
    height = expected_heights[station]
    for transverse in range(transverse_count):
      sample = field_nodes[grid_index(station, transverse)]
      speed = sample.mach / sqrt(
        1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach * sample.mach
      )
      local_flux = (
        _variable_entropy_normalized_density(
          sample.total_pressure_Pa,
          reference_total_pressure,
          sample.mach,
          sample.gamma,
        )
        * speed
        * cos(sample.flow_angle_rad)
        * height
      )
      inlet_sample = control_section.samples[transverse]
      inlet_speed = inlet_sample.mach / sqrt(
        1.0
        + 0.5 * (inlet_sample.gamma - 1.0)
        * inlet_sample.mach
        * inlet_sample.mach
      )
      inlet_flux = (
        _variable_entropy_normalized_density(
          source_pressure_by_fraction[transverse],
          reference_total_pressure,
          inlet_sample.mach,
          inlet_sample.gamma,
        )
        * inlet_speed
        * cos(inlet_sample.flow_angle_rad)
        * inlet_height
      )
      mass_residual = abs(local_flux - inlet_flux) / max(
        1.0e-12,
        abs(inlet_flux),
      )
      if station < 3:
        entrance_mass_flow.append(mass_residual)
      else:
        mass_flow.append(mass_residual)

  maximum_continuity = max(continuity, default=0.0)
  maximum_connector_continuity = max(connector_continuity, default=0.0)
  maximum_entrance_continuity = max(entrance_continuity, default=0.0)
  maximum_entropy = max(entropy, default=0.0)
  maximum_entrance_entropy = max(entrance_entropy, default=0.0)
  maximum_transverse = max(transverse_momentum, default=0.0)
  maximum_mass_flow = max(mass_flow, default=0.0)
  maximum_entrance_mass_flow = max(entrance_mass_flow, default=0.0)
  maximum_free_boundary_pressure = rechecked_condition.maximum_pressure_residual_Pa
  maximum_free_boundary_tangent = rechecked_condition.maximum_tangent_residual_rad
  continuity_verified = bool(
    cell_layout_verified
    and maximum_continuity <= continuity_tolerance
    and maximum_connector_continuity <= 10.0 * continuity_tolerance
  )
  entropy_transport_verified = maximum_entropy <= entropy_transport_tolerance
  free_boundary_condition_verified = bool(
    rechecked_condition.converged
    and maximum_free_boundary_pressure is not None
    and maximum_free_boundary_tangent is not None
  )
  residuals_verified = all(
    (
      _variable_entropy_metric_close(
        reported,
        measured,
        residual_tolerance,
      )
      for reported, measured in (
        (reference.maximum_continuity_residual, maximum_continuity),
        (reference.maximum_connector_continuity_residual, maximum_connector_continuity),
        (reference.maximum_entrance_continuity_residual, maximum_entrance_continuity),
        (reference.maximum_entropy_advection_residual, maximum_entropy),
        (
          reference.maximum_entrance_entropy_advection_residual,
          maximum_entrance_entropy,
        ),
        (reference.maximum_transverse_momentum_residual, maximum_transverse),
        (reference.maximum_mass_flow_residual, maximum_mass_flow),
        (
          reference.maximum_entrance_mass_flow_residual,
          maximum_entrance_mass_flow,
        ),
        (reference.maximum_free_boundary_pressure_residual_Pa, maximum_free_boundary_pressure),
        (reference.maximum_free_boundary_tangent_residual_rad, maximum_free_boundary_tangent),
      )
    )
  )
  reference_model_verified = bool(
    reference.status is MocMixedRegimeVariableEntropyFreeBoundaryStatus.CONVERGED_REFERENCE
    and reference.model == 'solver-owned-streamline-variable-entropy-free-boundary-reference'
    and reference.field is field
    and field.model == reference.model
    and field.physical_closure_verified is False
    and field.chain_promotion_blocked
    and reference.physical_closure_verified is False
    and reference.canonical_free_boundary_verified is False
    and reference.canonical_euler_verified is False
    and reference.chain_promotion_blocked
    and reference.production_claim_allowed is False
  )
  reported_flags_verified = bool(
    reference.source_streamline_mapping_verified == source_streamline_mapping_verified
    and reference.entropy_transport_verified == entropy_transport_verified
    and reference.continuity_verified == continuity_verified
    and reference.free_boundary_condition_verified
    == free_boundary_condition_verified
    and reference.field_topology_verified == field_topology_verified
    and residuals_verified
  )
  if not (
    continuity_verified
    and entropy_transport_verified
    and free_boundary_condition_verified
    and residuals_verified
    and reference_model_verified
  ):
    status = (
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.RESIDUAL_FAILURE
      if not (continuity_verified and entropy_transport_verified)
      else MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONSISTENCY_FAILURE
    )
    return _variable_entropy_measurement_failure(
      status,
      reference=reference,
      request_verified=True,
      handoff_verified=True,
      control_section_verified=True,
      source_streamline_mapping_verified=source_streamline_mapping_verified,
      field_boundary_verified=True,
      downstream_condition_verified=True,
      field_topology_verified=field_topology_verified,
      continuity_verified=continuity_verified,
      entropy_transport_verified=entropy_transport_verified,
      free_boundary_condition_verified=free_boundary_condition_verified,
      reported_flags_verified=reported_flags_verified,
      reference_model_verified=reference_model_verified,
      node_count=len(field_nodes),
      cell_count=len(field.cells),
      axial_station_count=axial_count,
      transverse_station_count=transverse_count,
      streamline_count=transverse_count,
      maximum_source_arc_residual_m=maximum_source_arc_residual,
      maximum_source_pressure_residual_Pa=maximum_source_pressure_residual,
      maximum_source_gamma_residual=maximum_source_gamma_residual,
      maximum_continuity_residual=maximum_continuity,
      maximum_connector_continuity_residual=maximum_connector_continuity,
      maximum_entrance_continuity_residual=maximum_entrance_continuity,
      maximum_entropy_advection_residual=maximum_entropy,
      maximum_entrance_entropy_advection_residual=maximum_entrance_entropy,
      maximum_transverse_momentum_residual=maximum_transverse,
      maximum_mass_flow_residual=maximum_mass_flow,
      maximum_entrance_mass_flow_residual=maximum_entrance_mass_flow,
      maximum_free_boundary_pressure_residual_Pa=maximum_free_boundary_pressure,
      maximum_free_boundary_tangent_residual_rad=maximum_free_boundary_tangent,
      message='independent variable-entropy residual or fidelity audit failed',
    )
  return MocMixedRegimeVariableEntropyFreeBoundaryMeasurement(
    status=MocMixedRegimeVariableEntropyFreeBoundaryMeasurementStatus.CONVERGED,
    reference=reference,
    request_verified=True,
    handoff_verified=True,
    control_section_verified=True,
    source_streamline_mapping_verified=True,
    field_boundary_verified=True,
    downstream_condition_verified=True,
    field_topology_verified=True,
    continuity_verified=True,
    entropy_transport_verified=True,
    free_boundary_condition_verified=True,
    reported_flags_verified=reported_flags_verified,
    reference_model_verified=True,
    physical_closure_verified=False,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    node_count=len(field_nodes),
    cell_count=len(field.cells),
    axial_station_count=axial_count,
    transverse_station_count=transverse_count,
    streamline_count=transverse_count,
    maximum_source_arc_residual_m=maximum_source_arc_residual,
    maximum_source_pressure_residual_Pa=maximum_source_pressure_residual,
    maximum_source_gamma_residual=maximum_source_gamma_residual,
    maximum_continuity_residual=maximum_continuity,
    maximum_connector_continuity_residual=maximum_connector_continuity,
    maximum_entrance_continuity_residual=maximum_entrance_continuity,
    maximum_entropy_advection_residual=maximum_entropy,
    maximum_entrance_entropy_advection_residual=maximum_entrance_entropy,
    maximum_transverse_momentum_residual=maximum_transverse,
    maximum_mass_flow_residual=maximum_mass_flow,
    maximum_entrance_mass_flow_residual=maximum_entrance_mass_flow,
    maximum_free_boundary_pressure_residual_Pa=maximum_free_boundary_pressure,
    maximum_free_boundary_tangent_residual_rad=maximum_free_boundary_tangent,
    message=(
      'independent measurement reproduced the solver-owned reverse entropy '
      'map, structured scalar field, closed mesh perimeter, ambient/tangency '
      'condition, and declared local residuals; canonical 2-D Euler/free-'
      'boundary closure remains pending'
    ),
  )
####


class MocShockCellMeasurementStatus(str, Enum):
  """Outcome of an independent MOC shock-cell measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  CHAIN_FAILURE = 'chain_failure'
####


class MocTerminalClosureMeasurementStatus(str, Enum):
  """Outcome of the independent first-cell terminal measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  SUPERSONIC_FAILURE = 'supersonic_failure'
  MIXED_REGIME_FAILURE = 'mixed_regime_failure'
####


@dataclass(frozen=True, slots=True)
class MocTerminalClosureObservation:
  """Terminal field and optional mixed-regime closure to be measured.

  The observation carries solver output as data only.  The measurement
  operator rechecks the terminal mesh, shock pressure loss, scalar seam,
  mixed-regime mesh, and closure metrics without accepting a solver object's
  convenience properties as proof.
  """

  terminal_field: MocTerminalShockCellFieldResult
  mixed_regime_closure: MocMixedRegimeClosureResult | None = None
####


@dataclass(frozen=True, slots=True)
class MocTerminalClosureMeasurement:
  """Independent acceptance gates for a terminal mixed-regime attachment."""

  status: MocTerminalClosureMeasurementStatus
  operator_id: str
  terminal_field_status: str | None
  mixed_regime_status: str | None
  supersonic_topology: MocTopologyResult
  mixed_regime_topology: MocTopologyResult
  terminal_shock_sample_count: int
  terminal_shock_edge_count: int
  terminal_shock_downstream_sample_count: int
  perimeter_sample_count: int
  supersonic_node_count: int
  supersonic_cell_count: int
  mixed_regime_node_count: int
  mixed_regime_cell_count: int
  terminal_normal_shock_verified: bool
  terminal_shock_geometry_verified: bool
  terminal_pressure_loss_verified: bool
  supersonic_patch_verified: bool
  mixed_regime_request_verified: bool
  mixed_regime_boundary_verified: bool
  mixed_regime_model_verified: bool
  downstream_condition_verified: bool
  physical_closure_verified: bool
  physical_termination_verified: bool
  chain_promotion_blocked: bool
  minimum_terminal_total_pressure_ratio: float | None
  maximum_terminal_total_pressure_ratio: float | None
  maximum_thermodynamic_residual: float | None
  maximum_harmonic_residual: float | None
  maximum_velocity_divergence_residual: float | None
  claim_status: str
  message: str
  mixed_regime_potential_model_verified: bool | None = None
  maximum_mass_conservation_residual: float | None = None
  maximum_boundary_normal_velocity_residual: float | None = None
  potential_circulation_residual: float | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalClosureMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible terminal measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'terminal_field_status': self.terminal_field_status,
      'mixed_regime_status': self.mixed_regime_status,
      'supersonic_topology': {
        'status': self.supersonic_topology.status.value,
        'connected': self.supersonic_topology.connected,
        'forms_closed_zone': self.supersonic_topology.forms_closed_zone,
        'boundary_edge_count': self.supersonic_topology.boundary_edge_count,
        'boundary_component_count': self.supersonic_topology.boundary_component_count,
        'nonmanifold_edge_count': self.supersonic_topology.nonmanifold_edge_count,
      },
      'mixed_regime_topology': {
        'status': self.mixed_regime_topology.status.value,
        'connected': self.mixed_regime_topology.connected,
        'forms_closed_zone': self.mixed_regime_topology.forms_closed_zone,
        'boundary_edge_count': self.mixed_regime_topology.boundary_edge_count,
        'boundary_component_count': self.mixed_regime_topology.boundary_component_count,
        'nonmanifold_edge_count': self.mixed_regime_topology.nonmanifold_edge_count,
      },
      'counts': {
        'terminal_shock_sample_count': self.terminal_shock_sample_count,
        'terminal_shock_edge_count': self.terminal_shock_edge_count,
        'terminal_shock_downstream_sample_count': self.terminal_shock_downstream_sample_count,
        'perimeter_sample_count': self.perimeter_sample_count,
        'supersonic_node_count': self.supersonic_node_count,
        'supersonic_cell_count': self.supersonic_cell_count,
        'mixed_regime_node_count': self.mixed_regime_node_count,
        'mixed_regime_cell_count': self.mixed_regime_cell_count,
      },
      'checks': {
        'terminal_normal_shock_verified': self.terminal_normal_shock_verified,
        'terminal_shock_geometry_verified': self.terminal_shock_geometry_verified,
        'terminal_pressure_loss_verified': self.terminal_pressure_loss_verified,
        'supersonic_patch_verified': self.supersonic_patch_verified,
        'mixed_regime_request_verified': self.mixed_regime_request_verified,
        'mixed_regime_boundary_verified': self.mixed_regime_boundary_verified,
        'mixed_regime_model_verified': self.mixed_regime_model_verified,
        'downstream_condition_verified': self.downstream_condition_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'physical_termination_verified': self.physical_termination_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'pressure': {
        'minimum_terminal_total_pressure_ratio': self.minimum_terminal_total_pressure_ratio,
        'maximum_terminal_total_pressure_ratio': self.maximum_terminal_total_pressure_ratio,
      },
      'residuals': {
        'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
        'maximum_harmonic_residual': self.maximum_harmonic_residual,
        'maximum_velocity_divergence_residual': self.maximum_velocity_divergence_residual,
        'maximum_mass_conservation_residual': self.maximum_mass_conservation_residual,
        'maximum_boundary_normal_velocity_residual': (
          self.maximum_boundary_normal_velocity_residual
        ),
        'potential_circulation_residual': self.potential_circulation_residual,
      },
      'mixed_regime_potential_model_verified': (
        self.mixed_regime_potential_model_verified
      ),
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocMixedRegimePotentialMeasurementStatus(str, Enum):
  """Outcome of the independent compressible-potential measurement."""

  CONVERGED = 'converged_reference_measurement'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'field_failure'
  BOUNDARY_FAILURE = 'boundary_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  RESIDUAL_FAILURE = 'potential_residual_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimePotentialMeasurement:
  """Independent checks for the explicit scalar potential reference field."""

  status: MocMixedRegimePotentialMeasurementStatus
  operator_id: str
  model: str | None
  radial_divisions: int | None
  node_count: int
  cell_count: int
  topology: MocTopologyResult
  boundary_verified: bool
  potential_layout_verified: bool
  reference_model_verified: bool
  downstream_condition_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  maximum_thermodynamic_residual: float | None
  maximum_mass_conservation_residual: float | None
  maximum_boundary_velocity_residual: float | None
  potential_circulation_residual: float | None
  maximum_mach: float | None
  message: str
  nonlinear_iteration_count: int = 0
  maximum_boundary_normal_velocity_residual: float | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimePotentialMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible independent potential-field measurement."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'model': self.model,
      'radial_divisions': self.radial_divisions,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'checks': {
        'boundary_verified': self.boundary_verified,
        'potential_layout_verified': self.potential_layout_verified,
        'reference_model_verified': self.reference_model_verified,
        'downstream_condition_verified': self.downstream_condition_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'residuals': {
        'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
        'maximum_mass_conservation_residual': self.maximum_mass_conservation_residual,
        'maximum_boundary_velocity_residual': self.maximum_boundary_velocity_residual,
        'maximum_boundary_normal_velocity_residual': (
          self.maximum_boundary_normal_velocity_residual
        ),
        'potential_circulation_residual': self.potential_circulation_residual,
      },
      'maximum_mach': self.maximum_mach,
      'nonlinear_iteration_count': self.nonlinear_iteration_count,
      'claim_status': (
        'independent-explicit-perimeter-potential-reference-measurement; '
        'not-canonical-free-boundary-validation'
      ),
      'message': self.message,
    }
  ####


class MocMixedRegimePlanarFreeBoundaryMeasurementStatus(str, Enum):
  """Outcome of the independent parameterized planar free-boundary audit."""

  CONVERGED = 'converged_parameterized_planar_free_boundary_measurement'
  INVALID_INPUT = 'invalid_input'
  CONTROL_SECTION_FAILURE = 'control_section_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  CONDITION_FAILURE = 'condition_failure'
  FIELD_FAILURE = 'field_failure'
  RESIDUAL_FAILURE = 'planar_free_boundary_residual_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarFreeBoundaryMeasurement:
  """Independent evidence for the bounded 2-D free-boundary reference.

  This operator treats the solver result as data.  It reconstructs the
  discrete envelope from the reported geometry, revalidates the terminal and
  control-section seams, rechecks the ambient/tangency condition, and routes
  the retained nonlinear field through the independent potential measurement.
  A passing record is local reference evidence only; it is not canonical MOC
  validation or permission to expose a production provider.
  """

  status: MocMixedRegimePlanarFreeBoundaryMeasurementStatus
  operator_id: str
  model: str | None
  solver_status: str | None
  potential_measurement_status: str | None
  node_count: int
  cell_count: int
  topology: MocTopologyResult
  request_verified: bool
  control_section_verified: bool
  perimeter_spec_verified: bool
  boundary_verified: bool
  downstream_condition_verified: bool
  field_measurement_verified: bool
  shape_geometry_verified: bool
  free_boundary_residual_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  maximum_boundary_normal_velocity_residual: float | None
  independent_boundary_normal_velocity_residual: float | None
  maximum_tangent_residual_rad: float | None
  maximum_pressure_residual_Pa: float | None
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'model': self.model,
      'solver_status': self.solver_status,
      'potential_measurement_status': self.potential_measurement_status,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'checks': {
        'request_verified': self.request_verified,
        'control_section_verified': self.control_section_verified,
        'perimeter_spec_verified': self.perimeter_spec_verified,
        'boundary_verified': self.boundary_verified,
        'downstream_condition_verified': self.downstream_condition_verified,
        'field_measurement_verified': self.field_measurement_verified,
        'shape_geometry_verified': self.shape_geometry_verified,
        'free_boundary_residual_verified': self.free_boundary_residual_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'residuals': {
        'maximum_boundary_normal_velocity_residual': (
          self.maximum_boundary_normal_velocity_residual
        ),
        'independent_boundary_normal_velocity_residual': (
          self.independent_boundary_normal_velocity_residual
        ),
        'maximum_tangent_residual_rad': self.maximum_tangent_residual_rad,
        'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      },
      'claim_status': (
        'independent-parameterized-2d-compressible-potential-free-boundary-'
        'reference-measurement; not-canonical-moc-validation'
      ),
      'message': self.message,
    }
  ####


class MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing parameterized planar free-boundary reruns."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'resolution_failure'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarFreeBoundaryRefinementCase:
  """One independently rerun planar free-boundary reference result.

  ``resolution`` is the number of retained free-boundary samples.  The
  operator checks that this metadata agrees with the typed result instead of
  allowing a caller to relabel one run as several resolutions.
  """

  resolution: int
  result: MocMixedRegimePlanarFreeBoundaryResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 4
    ):
      raise ValueError('resolution must be an integer of at least four')
    if not isinstance(
      self.result,
      MocMixedRegimePlanarFreeBoundaryResult,
    ):
      raise TypeError(
        'result must be a MocMixedRegimePlanarFreeBoundaryResult'
      )
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimePlanarFreeBoundaryRefinementMeasurement:
  """Independent numerical-sensitivity evidence for the planar reference.

  A passing result establishes repeatability of the explicitly parameterized
  compressible-potential envelope only.  It does not establish the canonical
  reflected-MOC mixed-regime boundary, external validation, or chain
  promotion.
  """

  status: MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus
  operator_id: str = (
    MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID
  )
  cases: tuple[MocMixedRegimePlanarFreeBoundaryRefinementCase, ...] = ()
  measurements: tuple[MocMixedRegimePlanarFreeBoundaryMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  perimeter_sample_counts: tuple[int, ...] = ()
  node_counts: tuple[int, ...] = ()
  cell_counts: tuple[int, ...] = ()
  resolution_order_verified: bool = False
  resolution_metadata_verified: bool = False
  request_consistent: bool = False
  control_section_consistent: bool = False
  solver_configuration_consistent: bool = False
  local_reference_closure_verified: bool = False
  shape_convergence_verified: bool = False
  centerline_speed_convergence_verified: bool = False
  mesh_area_convergence_verified: bool = False
  residuals_verified: bool = False
  shape_delta_residuals_m: tuple[float, ...] = ()
  centerline_speed_delta_residuals: tuple[float, ...] = ()
  mesh_area_delta_residuals_m2: tuple[float, ...] = ()
  maximum_normal_velocity_residuals: tuple[float | None, ...] = ()
  refinement_convergence_verified: bool = False
  physical_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    measurements = tuple(self.measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and measurements must have equal lengths')
    if any(
      not isinstance(
        case,
        MocMixedRegimePlanarFreeBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain planar free-boundary refinement cases'
      )
    if any(
      not isinstance(
        measurement,
        MocMixedRegimePlanarFreeBoundaryMeasurement,
      )
      for measurement in measurements
    ):
      raise TypeError(
        'measurements must contain planar free-boundary measurements'
    )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'measurements', measurements)
    results = tuple(case.result for case in cases)
    object.__setattr__(
      self,
      'resolutions',
      tuple(case.resolution for case in cases),
    )
    object.__setattr__(
      self,
      'perimeter_sample_counts',
      tuple(
        0
        if result.boundary is None
        else len(result.boundary.perimeter_points_m)
        for result in results
      ),
    )
    object.__setattr__(
      self,
      'node_counts',
      tuple(
        0 if result.field is None else len(result.field.nodes)
        for result in results
      ),
    )
    object.__setattr__(
      self,
      'cell_counts',
      tuple(
        0 if result.field is None else len(result.field.cells)
        for result in results
      ),
    )
    for name in (
      'shape_delta_residuals_m',
      'centerline_speed_delta_residuals',
      'mesh_area_delta_residuals_m2',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    residuals = tuple(
      None if value is None else float(value)
      for value in self.maximum_normal_velocity_residuals
    )
    if any(
      value is not None
      and (not isfinite(float(value)) or float(value) < 0.0)
      for value in residuals
    ):
      raise ValueError(
        'maximum_normal_velocity_residuals must contain finite nonnegative '
        'values or None'
      )
    object.__setattr__(self, 'maximum_normal_velocity_residuals', residuals)
    for name in (
      'resolution_order_verified',
      'resolution_metadata_verified',
      'request_consistent',
      'control_section_consistent',
      'solver_configuration_consistent',
      'local_reference_closure_verified',
      'shape_convergence_verified',
      'centerline_speed_convergence_verified',
      'mesh_area_convergence_verified',
      'residuals_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return (
      self.status
      is MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.CONVERGED
    )
  ####

  def as_report(self) -> dict[str, Any]:
    cases = [
      {
        'resolution': case.resolution,
        'measurement': measurement.as_report(),
      }
      for case, measurement in zip(self.cases, self.measurements, strict=True)
    ]
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'resolutions': list(self.resolutions),
      'perimeter_sample_counts': list(self.perimeter_sample_counts),
      'node_counts': list(self.node_counts),
      'cell_counts': list(self.cell_counts),
      'cases': cases,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'resolution_metadata_verified': self.resolution_metadata_verified,
        'request_consistent': self.request_consistent,
        'control_section_consistent': self.control_section_consistent,
        'solver_configuration_consistent': self.solver_configuration_consistent,
        'local_reference_closure_verified': self.local_reference_closure_verified,
        'shape_convergence_verified': self.shape_convergence_verified,
        'centerline_speed_convergence_verified': (
          self.centerline_speed_convergence_verified
        ),
        'mesh_area_convergence_verified': self.mesh_area_convergence_verified,
        'residuals_verified': self.residuals_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'residuals': {
        'shape_delta_residuals_m': list(self.shape_delta_residuals_m),
        'centerline_speed_delta_residuals': list(
          self.centerline_speed_delta_residuals
        ),
        'mesh_area_delta_residuals_m2': list(self.mesh_area_delta_residuals_m2),
        'maximum_normal_velocity_residuals': list(
          self.maximum_normal_velocity_residuals
        ),
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocMixedRegimeFreeBoundaryMeasurementStatus(str, Enum):
  """Outcome of the independent quasi-one-dimensional free-boundary audit."""

  CONVERGED = 'converged_solver_owned_free_boundary_measurement'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'terminal_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  CONDITION_FAILURE = 'condition_failure'
  FIELD_FAILURE = 'field_failure'
  RESIDUAL_FAILURE = 'residual_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFreeBoundaryMeasurement:
  """Independent evidence for the bounded free-boundary reference lane.

  The operator recomputes the scalar height root, perimeter geometry, selected
  ambient/tangency condition, radial field layout, and model-specific
  residuals.  When a control section is supplied, it also rechecks the
  retained section validation and, for the integrated-flux variant, the
  flux-to-height identity.  It deliberately reports the mesh divergence
  diagnostic without using it as a gate: this reference is
  quasi-one-dimensional, so that value is not evidence of a full
  two-dimensional MOC or Navier--Stokes field.
  """

  status: MocMixedRegimeFreeBoundaryMeasurementStatus
  operator_id: str
  model: str | None
  solver_status: str | None
  field_status: str | None
  node_count: int
  cell_count: int
  topology: MocTopologyResult
  ambient_pressure_Pa: float | None
  target_outlet_height_m: float | None
  outlet_height_m: float | None
  ambient_mach: float | None
  outlet_mach: float | None
  request_verified: bool
  perimeter_spec_verified: bool
  boundary_verified: bool
  downstream_condition_verified: bool
  closure_verified: bool
  field_model_verified: bool
  field_layout_verified: bool
  scalar_root_verified: bool
  mass_flow_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  height_residual_m: float | None
  pressure_residual_Pa: float | None
  mass_flow_residual: float | None
  free_boundary_pressure_residual_Pa: float | None
  free_boundary_tangent_residual_rad: float | None
  centerline_tangent_residual_rad: float | None
  outlet_pressure_residual_Pa: float | None
  free_boundary_geometry_residual_m: float | None
  maximum_thermodynamic_residual: float | None
  maximum_harmonic_residual: float | None
  maximum_velocity_divergence_residual: float | None
  claim_status: str
  message: str
  control_section_verified: bool | None = None
  control_section_flux_verified: bool | None = None
  control_section_flux_residual: float | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return JSON-compatible independent free-boundary evidence."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'model': self.model,
      'solver_status': self.solver_status,
      'field_status': self.field_status,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_outlet_height_m': self.target_outlet_height_m,
      'outlet_height_m': self.outlet_height_m,
      'ambient_mach': self.ambient_mach,
      'outlet_mach': self.outlet_mach,
      'checks': {
        'request_verified': self.request_verified,
        'perimeter_spec_verified': self.perimeter_spec_verified,
        'boundary_verified': self.boundary_verified,
        'downstream_condition_verified': self.downstream_condition_verified,
        'closure_verified': self.closure_verified,
        'field_model_verified': self.field_model_verified,
        'field_layout_verified': self.field_layout_verified,
        'scalar_root_verified': self.scalar_root_verified,
        'mass_flow_verified': self.mass_flow_verified,
        'control_section_verified': self.control_section_verified,
        'control_section_flux_verified': self.control_section_flux_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'residuals': {
        'height_residual_m': self.height_residual_m,
        'pressure_residual_Pa': self.pressure_residual_Pa,
        'mass_flow_residual': self.mass_flow_residual,
        'free_boundary_pressure_residual_Pa': self.free_boundary_pressure_residual_Pa,
        'free_boundary_tangent_residual_rad': self.free_boundary_tangent_residual_rad,
        'centerline_tangent_residual_rad': self.centerline_tangent_residual_rad,
        'outlet_pressure_residual_Pa': self.outlet_pressure_residual_Pa,
        'free_boundary_geometry_residual_m': self.free_boundary_geometry_residual_m,
        'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
        'maximum_harmonic_residual': self.maximum_harmonic_residual,
        'maximum_velocity_divergence_residual': self.maximum_velocity_divergence_residual,
        'control_section_flux_residual': self.control_section_flux_residual,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocMixedRegimeFreeBoundaryRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing independent free-boundary resolutions."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'resolution_failure'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFreeBoundaryRefinementCase:
  """One solver-owned free-boundary result at a declared resolution.

  ``resolution`` is caller-supplied metadata.  The refinement operator checks
  that the returned perimeter actually grows with that metadata, but it does
  not infer a resolution label from the returned geometry.
  """

  resolution: int
  result: MocMixedRegimeFreeBoundaryResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 1
    ):
      raise ValueError('resolution must be a positive integer')
    if not isinstance(self.result, MocMixedRegimeFreeBoundaryResult):
      raise TypeError(
        'result must be a MocMixedRegimeFreeBoundaryResult'
      )
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFreeBoundaryRefinementMeasurement:
  """Independent numerical-sensitivity evidence for the reference lane.

  A passing result means that the explicitly supplied quasi-one-dimensional
  free-boundary reference is stable over the declared resolutions.  It does
  not validate the missing reflected two-dimensional downstream law and can
  never promote the result into a continued shock-cell chain.
  """

  status: MocMixedRegimeFreeBoundaryRefinementMeasurementStatus
  operator_id: str = MOC_MIXED_REGIME_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID
  cases: tuple[MocMixedRegimeFreeBoundaryRefinementCase, ...] = ()
  measurements: tuple[MocMixedRegimeFreeBoundaryMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  ambient_pressure_Pa: tuple[float, ...] = ()
  effective_inlet_height_m: tuple[float, ...] = ()
  downstream_length_m: tuple[float, ...] = ()
  perimeter_sample_counts: tuple[int, ...] = ()
  radial_divisions: tuple[int, ...] = ()
  resolution_order_verified: bool = False
  request_consistent: bool = False
  solver_parameters_consistent: bool = False
  perimeter_resolution_verified: bool = False
  radial_divisions_consistent: bool = False
  case_measurements_verified: bool = False
  scalar_root_verified: bool = False
  mass_flow_verified: bool = False
  geometry_verified: bool = False
  local_reference_closure_verified: bool = False
  refinement_convergence_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  outlet_height_delta_residuals_m: tuple[float, ...] = ()
  height_root_residuals_m: tuple[float | None, ...] = ()
  free_boundary_geometry_residuals_m: tuple[float | None, ...] = ()
  mass_flow_residuals: tuple[float | None, ...] = ()
  maximum_velocity_divergence_residuals: tuple[float | None, ...] = ()
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    measurements = tuple(self.measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and measurements must have equal lengths')
    if any(
      not isinstance(case, MocMixedRegimeFreeBoundaryRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain MocMixedRegimeFreeBoundaryRefinementCase values'
      )
    if any(
      not isinstance(measurement, MocMixedRegimeFreeBoundaryMeasurement)
      for measurement in measurements
    ):
      raise TypeError(
        'measurements must contain MocMixedRegimeFreeBoundaryMeasurement values'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'measurements', measurements)
    object.__setattr__(
      self,
      'resolutions',
      tuple(case.resolution for case in cases),
    )
    results = tuple(case.result for case in cases)
    object.__setattr__(
      self,
      'ambient_pressure_Pa',
      tuple(float(result.ambient_pressure_Pa) for result in results),
    )
    object.__setattr__(
      self,
      'effective_inlet_height_m',
      tuple(float(result.effective_inlet_height_m) for result in results),
    )
    object.__setattr__(
      self,
      'downstream_length_m',
      tuple(float(result.downstream_length_m) for result in results),
    )
    object.__setattr__(
      self,
      'perimeter_sample_counts',
      tuple(
        0
        if result.boundary is None
        else len(result.boundary.perimeter_points_m)
        for result in results
      ),
    )
    object.__setattr__(
      self,
      'radial_divisions',
      tuple(
        0 if result.field is None else int(result.field.radial_divisions)
        for result in results
      ),
    )
    for name in (
      'outlet_height_delta_residuals_m',
      'height_root_residuals_m',
      'free_boundary_geometry_residuals_m',
      'mass_flow_residuals',
      'maximum_velocity_divergence_residuals',
    ):
      values = tuple(
        None if value is None else float(value)
        for value in getattr(self, name)
      )
      if any(
        value is not None
        and (not isfinite(value) or value < 0.0)
        for value in values
      ):
        raise ValueError(f'{name} must contain finite nonnegative values or None')
      object.__setattr__(self, name, values)
    for name in (
      'resolution_order_verified',
      'request_consistent',
      'solver_parameters_consistent',
      'perimeter_resolution_verified',
      'radial_divisions_consistent',
      'case_measurements_verified',
      'scalar_root_verified',
      'mass_flow_verified',
      'geometry_verified',
      'local_reference_closure_verified',
      'refinement_convergence_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return JSON-compatible free-boundary refinement evidence."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'resolutions': list(self.resolutions),
      'parameters': {
        'ambient_pressure_Pa': list(self.ambient_pressure_Pa),
        'effective_inlet_height_m': list(self.effective_inlet_height_m),
        'downstream_length_m': list(self.downstream_length_m),
        'perimeter_sample_counts': list(self.perimeter_sample_counts),
        'radial_divisions': list(self.radial_divisions),
      },
      'cases': [
        {
          'resolution': case.resolution,
          'result': case.result.as_report(),
          'measurement': measurement.as_report(),
        }
        for case, measurement in zip(
          self.cases,
          self.measurements,
          strict=True,
        )
      ],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'request_consistent': self.request_consistent,
        'solver_parameters_consistent': self.solver_parameters_consistent,
        'perimeter_resolution_verified': self.perimeter_resolution_verified,
        'radial_divisions_consistent': self.radial_divisions_consistent,
        'case_measurements_verified': self.case_measurements_verified,
        'scalar_root_verified': self.scalar_root_verified,
        'mass_flow_verified': self.mass_flow_verified,
        'geometry_verified': self.geometry_verified,
        'local_reference_closure_verified': self.local_reference_closure_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
      },
      'residuals': {
        'outlet_height_delta_residuals_m': list(self.outlet_height_delta_residuals_m),
        'height_root_residuals_m': list(self.height_root_residuals_m),
        'free_boundary_geometry_residuals_m': list(
          self.free_boundary_geometry_residuals_m
        ),
        'mass_flow_residuals': list(self.mass_flow_residuals),
        'maximum_velocity_divergence_residuals': list(
          self.maximum_velocity_divergence_residuals
        ),
      },
      'physical_closure_verified': self.local_reference_closure_verified,
      'canonical_reflected_moc_closure_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocMixedRegimeControlSectionMeasurementStatus(str, Enum):
  """Outcome of the independent scalar control-section audit."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'terminal_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  STATE_FAILURE = 'state_failure'
  FLUX_FAILURE = 'flux_failure'
####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeControlSectionMeasurement:
  """Independent evidence for an explicit downstream control section.

  This operator remeasures the section geometry, terminal placement, scalar
  isentropic state, total-pressure lineage, and oriented mass-flux proxy.  It
  does not call the solver-owned control-section validator and it does not
  treat a passing section as a closed mixed-regime field or chain cell.
  """

  status: MocMixedRegimeControlSectionMeasurementStatus
  operator_id: str
  sample_count: int
  request_verified: bool
  geometry_verified: bool
  state_verified: bool
  flux_verified: bool
  terminal_equivalent_verified: bool
  section_measure_m: float | None
  mass_flux_proxy: float | None
  minimum_normal_flux_factor: float | None
  maximum_total_pressure_gain_Pa: float | None
  maximum_isentropic_residual: float | None
  minimum_downstream_terminal_margin_m: float | None
  maximum_terminal_state_residual: float | None
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeControlSectionMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'sample_count': self.sample_count,
      'checks': {
        'request_verified': self.request_verified,
        'geometry_verified': self.geometry_verified,
        'state_verified': self.state_verified,
        'flux_verified': self.flux_verified,
        'terminal_equivalent_verified': self.terminal_equivalent_verified,
      },
      'section_measure_m': self.section_measure_m,
      'mass_flux_proxy': self.mass_flux_proxy,
      'minimum_normal_flux_factor': self.minimum_normal_flux_factor,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'maximum_isentropic_residual': self.maximum_isentropic_residual,
      'minimum_downstream_terminal_margin_m': self.minimum_downstream_terminal_margin_m,
      'maximum_terminal_state_residual': self.maximum_terminal_state_residual,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _control_section_measurement_failure(
  status: MocMixedRegimeControlSectionMeasurementStatus,
  *,
  sample_count: int = 0,
  request_verified: bool = False,
  geometry_verified: bool = False,
  state_verified: bool = False,
  flux_verified: bool = False,
  terminal_equivalent_verified: bool = False,
  section_measure_m: float | None = None,
  mass_flux_proxy: float | None = None,
  minimum_normal_flux_factor: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  maximum_isentropic_residual: float | None = None,
  minimum_downstream_terminal_margin_m: float | None = None,
  maximum_terminal_state_residual: float | None = None,
  message: str,
) -> MocMixedRegimeControlSectionMeasurement:
  return MocMixedRegimeControlSectionMeasurement(
    status=status,
    operator_id=MOC_MIXED_REGIME_CONTROL_SECTION_OPERATOR_ID,
    sample_count=sample_count,
    request_verified=request_verified,
    geometry_verified=geometry_verified,
    state_verified=state_verified,
    flux_verified=flux_verified,
    terminal_equivalent_verified=terminal_equivalent_verified,
    section_measure_m=section_measure_m,
    mass_flux_proxy=mass_flux_proxy,
    minimum_normal_flux_factor=minimum_normal_flux_factor,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    maximum_isentropic_residual=maximum_isentropic_residual,
    minimum_downstream_terminal_margin_m=minimum_downstream_terminal_margin_m,
    maximum_terminal_state_residual=maximum_terminal_state_residual,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status=(
      'independent-mixed-regime-control-section-measurement; '
      'not-a-2d-field-or-chain-validation'
    ),
    message=message,
  )
####


def measure_mixed_regime_control_section(
  request: MocMixedRegimePerimeterRequest,
  section: MocMixedRegimeControlSection | None,
  *,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
) -> MocMixedRegimeControlSectionMeasurement:
  """Independently measure a scalar section without using solver verdicts."""

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _control_section_measurement_failure(
      MocMixedRegimeControlSectionMeasurementStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  if section is None:
    return _control_section_measurement_failure(
      MocMixedRegimeControlSectionMeasurementStatus.INVALID_INPUT,
      request_verified=True,
      message=(
        'independent control-section measurement requires explicit section '
        'geometry and scalar samples'
      ),
    )
  if not isinstance(section, MocMixedRegimeControlSection):
    return _control_section_measurement_failure(
      MocMixedRegimeControlSectionMeasurementStatus.INVALID_INPUT,
      request_verified=True,
      message='section must be a MocMixedRegimeControlSection or None',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  terminal = request.terminal
  upstream_state = terminal.upstream_state
  request_verified = bool(
    upstream_state is not None
    and terminal.shock_point_m == request.terminal_point_m
    and terminal.downstream_mach == request.terminal_downstream_mach
    and terminal.downstream_flow_angle_rad == request.terminal_downstream_flow_angle_rad
    and terminal.downstream_pressure_Pa == request.terminal_downstream_pressure_Pa
    and terminal.downstream_total_pressure_Pa == request.terminal_downstream_total_pressure_Pa
    and terminal.total_pressure_ratio == request.terminal_total_pressure_ratio
  )
  if not request_verified:
    return _control_section_measurement_failure(
      MocMixedRegimeControlSectionMeasurementStatus.TERMINAL_FAILURE,
      sample_count=len(section.samples),
      request_verified=False,
      message='request does not retain a complete exact terminal seam',
    )
  assert upstream_state is not None

  points = section.points_m
  samples = section.samples
  normal_angle = float(section.normal_angle_rad)
  tangent = (-sin(normal_angle), cos(normal_angle))
  normal = (cos(normal_angle), sin(normal_angle))
  point_match = len(points) == len(samples) and all(
    hypot(sample.point_m[0] - point[0], sample.point_m[1] - point[1])
    <= float(position_tolerance_m)
    for sample, point in zip(samples, points, strict=True)
  )
  normal_coordinates = tuple(
    point[0] * normal[0] + point[1] * normal[1]
    for point in points
  )
  tangent_coordinates = tuple(
    point[0] * tangent[0] + point[1] * tangent[1]
    for point in points
  )
  lengths = tuple(
    hypot(second[0] - first[0], second[1] - first[1])
    for first, second in zip(points, points[1:])
  )
  section_measure = fsum(lengths)
  geometry_verified = bool(
    len(points) >= 2
    and point_match
    and all(all(isfinite(value) for value in point) for point in points)
    and isfinite(normal_angle)
    and isfinite(section_measure)
    and section_measure > float(position_tolerance_m)
    and max(normal_coordinates, default=0.0)
    - min(normal_coordinates, default=0.0)
    <= float(position_tolerance_m)
    and all(
      second > first + float(position_tolerance_m)
      for first, second in zip(tangent_coordinates, tangent_coordinates[1:])
    )
    and all(length > float(position_tolerance_m) for length in lengths)
  )
  terminal_x, terminal_y = request.terminal_point_m
  terminal_angle = request.terminal_downstream_flow_angle_rad
  margins = tuple(
    (point[0] - terminal_x) * cos(terminal_angle)
    + (point[1] - terminal_y) * sin(terminal_angle)
    for point in points
  )
  minimum_margin = min(margins, default=None)
  geometry_verified = bool(
    geometry_verified
    and minimum_margin is not None
    and minimum_margin > float(position_tolerance_m)
  )
  try:
    flux_factors = tuple(
      cos(sample.flow_angle_rad - normal_angle)
      for sample in samples
    )
    minimum_flux_factor = min(flux_factors, default=None)
    mass_densities = tuple(
      sample.total_pressure_Pa
      * _free_boundary_mass_flux_measurement(sample.mach, sample.gamma)
      * projection
      for sample, projection in zip(samples, flux_factors, strict=True)
    )
    mass_flux = fsum(
      0.5 * (first + second) * length
      for first, second, length in zip(
        mass_densities,
        mass_densities[1:],
        lengths,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    minimum_flux_factor = None
    mass_flux = None
  flux_verified = bool(
    minimum_flux_factor is not None
    and minimum_flux_factor > float(normal_flux_tolerance)
    and mass_flux is not None
    and isfinite(mass_flux)
    and mass_flux > 0.0
  )

  total_pressure = request.terminal_downstream_total_pressure_Pa
  terminal_mach = request.terminal_downstream_mach
  maximum_isentropic_residual = max(
    (
      _relative_value_residual(
        _scalar_total_pressure(
          sample.mach,
          sample.gamma,
          sample.static_pressure_Pa,
        ),
        sample.total_pressure_Pa,
      )
      for sample in samples
    ),
    default=None,
  )
  maximum_total_pressure_gain = max(
    (
      max(0.0, sample.total_pressure_Pa - total_pressure)
      for sample in samples
    ),
    default=None,
  )
  maximum_terminal_state_residual = max(
    (
      max(
        abs(sample.mach - terminal_mach),
        abs(sample.flow_angle_rad - terminal_angle),
        _relative_value_residual(sample.total_pressure_Pa, total_pressure),
      )
      for sample in samples
    ),
    default=None,
  )
  state_verified = bool(
    samples
    and all(
      sample.gamma > 1.0
      and abs(sample.gamma - upstream_state.gamma) <= float(state_tolerance)
      and 0.0 < sample.mach < 1.0
      for sample in samples
    )
    and maximum_isentropic_residual is not None
    and maximum_isentropic_residual <= float(state_tolerance)
    and maximum_total_pressure_gain is not None
    and maximum_total_pressure_gain <= float(pressure_tolerance) * max(
      1.0,
      abs(total_pressure),
    )
  )
  terminal_equivalent_verified = bool(
    state_verified
    and maximum_terminal_state_residual is not None
    and maximum_terminal_state_residual <= float(state_tolerance)
  )
  metrics = {
    'sample_count': len(samples),
    'request_verified': request_verified,
    'geometry_verified': geometry_verified,
    'state_verified': state_verified,
    'flux_verified': flux_verified,
    'terminal_equivalent_verified': terminal_equivalent_verified,
    'section_measure_m': section_measure,
    'mass_flux_proxy': mass_flux,
    'minimum_normal_flux_factor': minimum_flux_factor,
    'maximum_total_pressure_gain_Pa': maximum_total_pressure_gain,
    'maximum_isentropic_residual': maximum_isentropic_residual,
    'minimum_downstream_terminal_margin_m': minimum_margin,
    'maximum_terminal_state_residual': maximum_terminal_state_residual,
  }
  if not geometry_verified:
    status = MocMixedRegimeControlSectionMeasurementStatus.GEOMETRY_FAILURE
    message = 'independent control-section geometry or downstream placement failed'
  elif not flux_verified:
    status = MocMixedRegimeControlSectionMeasurementStatus.FLUX_FAILURE
    message = 'independent control-section oriented mass-flux gate failed'
  elif not state_verified:
    status = MocMixedRegimeControlSectionMeasurementStatus.STATE_FAILURE
    message = 'independent control-section scalar state/pressure-lineage gate failed'
  else:
    status = MocMixedRegimeControlSectionMeasurementStatus.CONVERGED
    message = (
      'independent control-section geometry, placement, scalar state, '
      'pressure-lineage, and oriented flux gates passed; this is not a '
      'two-dimensional mixed-regime field or chain acceptance'
    )
  return _control_section_measurement_failure(
    status,
    message=message,
    **metrics,
  )
####


class MocCausticRemeshMeasurementStatus(str, Enum):
  """Outcome of the independent bounded caustic-remesh measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  EVENT_FAILURE = 'event_failure'
  UPSTREAM_FAILURE = 'upstream_failure'
  SHOCK_FAILURE = 'shock_failure'
  FIELD_FAILURE = 'field_failure'
  SEAM_FAILURE = 'seam_failure'
####


@dataclass(frozen=True, slots=True)
class MocCausticRemeshObservation:
  """Solver output and optional domain-bounded bridge for measurement.

  The remesh result is treated as data.  When ``upstream_bridge`` is supplied,
  the operator resamples that bridge along the retained shock path, including
  a solver-reported failed sample when present.  This makes an open bridge
  gap independently observable instead of accepting the remesh object's
  cached coupling flags.  When ``incoming_handoff`` is supplied, the returned
  field must also carry the exact prior chain states and total pressures.
  """

  remesh_result: MocCausticShockRemeshResult
  upstream_bridge: MocCausticUpstreamBridge | None = None
  incoming_handoff: tuple[MocChainBoundarySample, ...] | None = None
####


@dataclass(frozen=True, slots=True)
class MocCausticRemeshMeasurement:
  """Independent gates for a bounded caustic shock/new-family remesh.

  ``CONVERGED`` means the bounded remesh data passed this operator's local
  event, shock, field, and optional bridge checks.  It is intentionally not a
  physical first-cell closure result: the old-family/new-family seam and the
  downstream ambient/mixed-regime boundary remain outside this operator.
  """

  status: MocCausticRemeshMeasurementStatus
  operator_id: str
  remesh_status: str | None
  bridge_status: str | None
  event_point_m: Point | None
  shock_sample_count: int
  shock_fit_sample_count: int
  field_node_count: int
  field_cell_count: int
  incoming_handoff_sample_count: int
  incoming_handoff_verified: bool | None
  field_topology: MocTopologyResult
  first_missing_sample_index: int | None
  first_missing_point_m: Point | None
  event_point_verified: bool
  event_state_verified: bool
  event_pressure_verified: bool
  local_bridge_verified: bool
  shock_geometry_verified: bool
  shock_fit_verified: bool
  shock_pressure_loss_verified: bool
  upstream_field_verified: bool
  upstream_bridge_verified: bool | None
  field_topology_verified: bool
  field_boundary_verified: bool
  field_state_carry_verified: bool
  field_residuals_verified: bool
  downstream_field_verified: bool
  remesh_seam_verified: bool
  bounded_remesh_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  maximum_shock_angle_residual_rad: float | None
  maximum_field_geometry_residual_m: float | None
  maximum_field_invariant_residual: float | None
  minimum_total_pressure_ratio: float | None
  maximum_total_pressure_ratio: float | None
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocCausticRemeshMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible bounded-remesh measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'remesh_status': self.remesh_status,
      'bridge_status': self.bridge_status,
      'event_point_m': self.event_point_m,
      'counts': {
        'shock_sample_count': self.shock_sample_count,
        'shock_fit_sample_count': self.shock_fit_sample_count,
        'field_node_count': self.field_node_count,
        'field_cell_count': self.field_cell_count,
        'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      },
      'field_topology': {
        'status': self.field_topology.status.value,
        'connected': self.field_topology.connected,
        'forms_closed_zone': self.field_topology.forms_closed_zone,
        'boundary_edge_count': self.field_topology.boundary_edge_count,
        'boundary_component_count': self.field_topology.boundary_component_count,
        'nonmanifold_edge_count': self.field_topology.nonmanifold_edge_count,
      },
      'first_missing_sample_index': self.first_missing_sample_index,
      'first_missing_point_m': self.first_missing_point_m,
      'checks': {
        'event_point_verified': self.event_point_verified,
        'event_state_verified': self.event_state_verified,
        'event_pressure_verified': self.event_pressure_verified,
        'local_bridge_verified': self.local_bridge_verified,
        'shock_geometry_verified': self.shock_geometry_verified,
        'shock_fit_verified': self.shock_fit_verified,
        'shock_pressure_loss_verified': self.shock_pressure_loss_verified,
        'upstream_field_verified': self.upstream_field_verified,
        'upstream_bridge_verified': self.upstream_bridge_verified,
        'incoming_handoff_verified': self.incoming_handoff_verified,
        'field_topology_verified': self.field_topology_verified,
        'field_boundary_verified': self.field_boundary_verified,
        'field_state_carry_verified': self.field_state_carry_verified,
        'field_residuals_verified': self.field_residuals_verified,
        'downstream_field_verified': self.downstream_field_verified,
        'remesh_seam_verified': self.remesh_seam_verified,
        'bounded_remesh_verified': self.bounded_remesh_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'residuals': {
        'maximum_shock_angle_residual_rad': self.maximum_shock_angle_residual_rad,
        'maximum_field_geometry_residual_m': self.maximum_field_geometry_residual_m,
        'maximum_field_invariant_residual': self.maximum_field_invariant_residual,
      },
      'pressure': {
        'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
        'maximum_total_pressure_ratio': self.maximum_total_pressure_ratio,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainRemeshMeasurementStatus(str, Enum):
  """Outcome of the independent reflected-domain remesh measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  INCOMING_TRACE_FAILURE = 'incoming_trace_failure'
  REFLECTION_SEAM_FAILURE = 'reflection_seam_failure'
  SOURCE_FAILURE = 'source_failure'
  FIELD_FAILURE = 'field_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainRemeshMeasurement:
  """Independent gates for one bounded reflected-domain source remesh.

  The remesh result is treated as raw solver data.  This operator repeats the
  incoming ``C-`` trace, polarity, reflection seam, source-row, topology, and
  source sampling checks without accepting the result object's cached boolean
  flags as evidence.  A converged measurement is only a bounded Cauchy-field
  result; it does not close the downstream free boundary or promote a chain
  cell.
  """

  status: MocReflectedDomainRemeshMeasurementStatus
  operator_id: str
  remesh_status: str | None
  incoming_trace_polarity: str | None
  incoming_trace_sample_count: int
  centerline_source_count: int
  outer_source_count: int
  source_node_count: int
  source_cell_count: int
  source_topology: MocTopologyResult
  result_status_verified: bool
  incoming_trace_verified: bool
  polarity_verified: bool
  reflection_seam_verified: bool
  centerline_source_verified: bool
  outer_source_verified: bool
  total_pressure_verified: bool
  source_topology_verified: bool
  source_sampling_verified: bool
  bounded_remesh_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainRemeshMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible independent remesh measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'remesh_status': self.remesh_status,
      'incoming_trace_polarity': self.incoming_trace_polarity,
      'counts': {
        'incoming_trace_sample_count': self.incoming_trace_sample_count,
        'centerline_source_count': self.centerline_source_count,
        'outer_source_count': self.outer_source_count,
        'source_node_count': self.source_node_count,
        'source_cell_count': self.source_cell_count,
      },
      'source_topology': {
        'status': self.source_topology.status.value,
        'connected': self.source_topology.connected,
        'forms_closed_zone': self.source_topology.forms_closed_zone,
        'boundary_edge_count': self.source_topology.boundary_edge_count,
        'boundary_component_count': self.source_topology.boundary_component_count,
        'nonmanifold_edge_count': self.source_topology.nonmanifold_edge_count,
      },
      'checks': {
        'result_status_verified': self.result_status_verified,
        'incoming_trace_verified': self.incoming_trace_verified,
        'polarity_verified': self.polarity_verified,
        'reflection_seam_verified': self.reflection_seam_verified,
        'centerline_source_verified': self.centerline_source_verified,
        'outer_source_verified': self.outer_source_verified,
        'total_pressure_verified': self.total_pressure_verified,
        'source_topology_verified': self.source_topology_verified,
        'source_sampling_verified': self.source_sampling_verified,
        'bounded_remesh_verified': self.bounded_remesh_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainOuterSourceMeasurementStatus(str, Enum):
  """Outcome of the independent outer-source-curve measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'seed_failure'
  BOUNDARY_FAILURE = 'boundary_failure'
  FIELD_FAILURE = 'field_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainOuterSourceMeasurement:
  """Independent gates for a generated reflected-domain outer source.

  The measurement reconstructs the ambient boundary and characteristic strip
  from the returned raw rows.  It does not accept the solver's cached
  convergence flags as evidence and does not promote the source field to a
  physical shock-cell solution.
  """

  status: MocReflectedDomainOuterSourceMeasurementStatus
  operator_id: str
  solver_status: str | None
  centerline_source_count: int
  outer_source_count: int
  boundary_point_count: int
  source_node_count: int
  source_cell_count: int
  source_topology: MocTopologyResult
  ambient_boundary: MocAmbientPressureBoundaryResult | None
  result_status_verified: bool
  seed_verified: bool
  centerline_source_verified: bool
  outer_source_verified: bool
  pressure_lineage_verified: bool
  ambient_boundary_verified: bool
  source_topology_verified: bool
  source_sampling_verified: bool
  bounded_source_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainOuterSourceMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'solver_status': self.solver_status,
      'counts': {
        'centerline_source_count': self.centerline_source_count,
        'outer_source_count': self.outer_source_count,
        'boundary_point_count': self.boundary_point_count,
        'source_node_count': self.source_node_count,
        'source_cell_count': self.source_cell_count,
      },
      'source_topology': {
        'status': self.source_topology.status.value,
        'connected': self.source_topology.connected,
        'forms_closed_zone': self.source_topology.forms_closed_zone,
        'boundary_edge_count': self.source_topology.boundary_edge_count,
        'boundary_component_count': self.source_topology.boundary_component_count,
        'nonmanifold_edge_count': self.source_topology.nonmanifold_edge_count,
      },
      'ambient_boundary': (
        None
        if self.ambient_boundary is None
        else self.ambient_boundary.as_report()
      ),
      'checks': {
        'result_status_verified': self.result_status_verified,
        'seed_verified': self.seed_verified,
        'centerline_source_verified': self.centerline_source_verified,
        'outer_source_verified': self.outer_source_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'ambient_boundary_verified': self.ambient_boundary_verified,
        'source_topology_verified': self.source_topology_verified,
        'source_sampling_verified': self.source_sampling_verified,
        'bounded_source_verified': self.bounded_source_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainAlternatingSourceMeasurementStatus(str, Enum):
  """Outcome of the independent alternating-source-band measurement."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  INCOMING_TRACE_FAILURE = 'incoming_trace_failure'
  SEED_FAILURE = 'seed_failure'
  ANCHOR_FAILURE = 'anchor_failure'
  CENTERLINE_FAILURE = 'centerline_failure'
  BOUNDARY_FAILURE = 'boundary_failure'
  FIELD_FAILURE = 'field_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingSourceMeasurement:
  """Independent gates for an alternating reflected-domain source band."""

  status: MocReflectedDomainAlternatingSourceMeasurementStatus
  operator_id: str
  solver_status: str | None
  incoming_trace_sample_count: int
  source_sample_count: int
  source_node_count: int
  source_cell_count: int
  source_topology: MocTopologyResult
  incoming_trace_verified: bool
  polarity_verified: bool
  seed_verified: bool
  reflection_anchor_verified: bool
  centerline_recomputed_verified: bool
  boundary_recomputed_verified: bool
  pressure_lineage_verified: bool
  ambient_boundary_verified: bool
  alternating_seam_verified: bool
  source_topology_verified: bool
  source_sampling_verified: bool
  bounded_source_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainAlternatingSourceMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'solver_status': self.solver_status,
      'counts': {
        'incoming_trace_sample_count': self.incoming_trace_sample_count,
        'source_sample_count': self.source_sample_count,
        'source_node_count': self.source_node_count,
        'source_cell_count': self.source_cell_count,
      },
      'source_topology': {
        'status': self.source_topology.status.value,
        'connected': self.source_topology.connected,
        'forms_closed_zone': self.source_topology.forms_closed_zone,
        'boundary_edge_count': self.source_topology.boundary_edge_count,
        'boundary_component_count': self.source_topology.boundary_component_count,
        'nonmanifold_edge_count': self.source_topology.nonmanifold_edge_count,
      },
      'checks': {
        'incoming_trace_verified': self.incoming_trace_verified,
        'polarity_verified': self.polarity_verified,
        'seed_verified': self.seed_verified,
        'reflection_anchor_verified': self.reflection_anchor_verified,
        'centerline_recomputed_verified': self.centerline_recomputed_verified,
        'boundary_recomputed_verified': self.boundary_recomputed_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'ambient_boundary_verified': self.ambient_boundary_verified,
        'alternating_seam_verified': self.alternating_seam_verified,
        'source_topology_verified': self.source_topology_verified,
        'source_sampling_verified': self.source_sampling_verified,
        'bounded_source_verified': self.bounded_source_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus(str, Enum):
  """Outcome of independently auditing an alternating-source shock field."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'source_failure'
  SHOCK_FAILURE = 'shock_failure'
  FIELD_FAILURE = 'field_failure'
  ENVELOPE_FAILURE = 'envelope_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingPhysicalFieldMeasurement:
  """Independent evidence for one alternating-source physical field.

  The source-band audit and the physical-field audit are kept separate in the
  report.  The envelope is recomputed from the stored amplitude and raw shock
  samples; a successful physical field therefore cannot hide a changed
  upstream band or a changed downstream turn law.  This measurement remains
  non-promotable because the local envelope is a research boundary condition,
  not the canonical reflected-plume free-boundary law.
  """

  status: MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus
  operator_id: str
  solver_status: str | None
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None
  field_measurement: MocPhysicalFieldChainMeasurement | None
  source_field_verified: bool
  attachment_point_verified: bool
  attachment_pressure_verified: bool
  zero_strength_attachment_verified: bool
  envelope_verified: bool
  shock_curve_verified: bool
  physical_field_verified: bool
  state_sampling_verified: bool
  upstream_coupling_verified: bool
  incoming_handoff_verified: bool
  bounded_physical_field_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  compression_amplitude_rad: float | None
  shock_sample_count: int
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'solver_status': self.solver_status,
      'source_measurement': (
        None
        if self.source_measurement is None
        else self.source_measurement.as_report()
      ),
      'field_measurement': (
        None
        if self.field_measurement is None
        else self.field_measurement.as_report()
      ),
      'checks': {
        'source_field_verified': self.source_field_verified,
        'attachment_point_verified': self.attachment_point_verified,
        'attachment_pressure_verified': self.attachment_pressure_verified,
        'zero_strength_attachment_verified': self.zero_strength_attachment_verified,
        'envelope_verified': self.envelope_verified,
        'shock_curve_verified': self.shock_curve_verified,
        'physical_field_verified': self.physical_field_verified,
        'state_sampling_verified': self.state_sampling_verified,
        'upstream_coupling_verified': self.upstream_coupling_verified,
        'incoming_handoff_verified': self.incoming_handoff_verified,
        'bounded_physical_field_verified': self.bounded_physical_field_verified,
      },
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'compression_amplitude_rad': self.compression_amplitude_rad,
      'shock_sample_count': self.shock_sample_count,
      'canonical_reflected_domain_closed': False,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainSolverOwnedFirstCellMeasurementStatus(str, Enum):
  """Outcome of independently auditing the solver-owned first cell."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'source_failure'
  TRIAL_FAILURE = 'trial_failure'
  CLOSURE_FAILURE = 'closure_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainSolverOwnedFirstCellMeasurement:
  """Independent evidence for the source-owned first-cell endpoint shoot.

  This operator remeasures the generated source band, every retained physical
  trial, and the selected endpoint residual.  A typed no-bracket result can
  therefore be accepted as a reproducible research audit while remaining
  explicitly non-physical and non-promotable.
  """

  status: MocReflectedDomainSolverOwnedFirstCellMeasurementStatus
  operator_id: str
  solver_status: str | None
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None
  trial_count: int
  target_centerline_verified: bool
  amplitude_bracket_verified: bool
  trial_amplitudes_verified: bool
  trial_residuals_verified: bool
  selected_trial_verified: bool
  selected_field_measurement: (
    MocReflectedDomainAlternatingPhysicalFieldMeasurement | None
  )
  selected_field_verified: bool
  scalar_endpoint_verified: bool
  physical_closure_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  external_validation_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_isolation_verified: bool
  selected_amplitude: float | None
  selected_residual_m: float | None
  minimum_absolute_residual_m: float | None
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'solver_status': self.solver_status,
      'source_measurement': (
        None
        if self.source_measurement is None
        else self.source_measurement.as_report()
      ),
      'trial_count': self.trial_count,
      'selected_amplitude': self.selected_amplitude,
      'selected_residual_m': self.selected_residual_m,
      'minimum_absolute_residual_m': self.minimum_absolute_residual_m,
      'selected_field_measurement': (
        None
        if self.selected_field_measurement is None
        else self.selected_field_measurement.as_report()
      ),
      'checks': {
        'target_centerline_verified': self.target_centerline_verified,
        'amplitude_bracket_verified': self.amplitude_bracket_verified,
        'trial_amplitudes_verified': self.trial_amplitudes_verified,
        'trial_residuals_verified': self.trial_residuals_verified,
        'selected_trial_verified': self.selected_trial_verified,
        'selected_field_verified': self.selected_field_verified,
        'scalar_endpoint_verified': self.scalar_endpoint_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'canonical_reflected_domain_closed': False,
      'claim_status': (
        'independent-solver-owned-first-cell-audit; '
        'local-research-reference-only'
      ),
      'message': self.message,
    }
  ####


class MocReflectedDomainGlobalShockRemeshMeasurementStatus(str, Enum):
  """Outcome of independently auditing a global reflected-shock sweep."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'source_failure'
  ATTEMPT_FAILURE = 'attempt_failure'
  CLOSURE_FAILURE = 'closure_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalShockRemeshMeasurement:
  """Independent evidence for a bounded global reflected-shock sweep.

  The operator remeasures the source band and every retained first-cell
  attempt.  It accepts a reproducible no-endpoint sweep as research evidence,
  but never treats a locally aligned endpoint as canonical reflected-Euler
  closure or as permission to promote a continued chain cell.
  """

  status: MocReflectedDomainGlobalShockRemeshMeasurementStatus
  operator_id: str
  solver_status: str | None
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None
  attempt_count: int
  attempt_measurements: (
    tuple[MocReflectedDomainSolverOwnedFirstCellMeasurement, ...]
  )
  source_field_verified: bool
  attempt_identity_verified: bool
  attempt_shape_verified: bool
  attempt_residuals_verified: bool
  selected_attempt_verified: bool
  global_endpoint_verified: bool
  no_endpoint_closure_verified: bool
  physical_closure_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  external_validation_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_isolation_verified: bool
  selected_residual_m: float | None
  endpoint_tolerance_m: float
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainGlobalShockRemeshMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'solver_status': self.solver_status,
      'source_measurement': (
        None
        if self.source_measurement is None
        else self.source_measurement.as_report()
      ),
      'attempt_count': self.attempt_count,
      'attempt_measurements': tuple(
        measurement.as_report()
        for measurement in self.attempt_measurements
      ),
      'checks': {
        'source_field_verified': self.source_field_verified,
        'attempt_identity_verified': self.attempt_identity_verified,
        'attempt_shape_verified': self.attempt_shape_verified,
        'attempt_residuals_verified': self.attempt_residuals_verified,
        'selected_attempt_verified': self.selected_attempt_verified,
        'global_endpoint_verified': self.global_endpoint_verified,
        'no_endpoint_closure_verified': self.no_endpoint_closure_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'selected_residual_m': self.selected_residual_m,
      'endpoint_tolerance_m': self.endpoint_tolerance_m,
      'canonical_reflected_domain_closed': False,
      'claim_status': (
        'independent-global-reflected-shock-remesh-audit; '
        'bounded-research-sweep-only'
      ),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellObservation:
  """Raw field boundaries and mesh supplied to the measurement operator.

  The observation intentionally contains no solver status.  A planner mock
  and a solver-generated field therefore go through exactly the same
  extraction and topology checks, while their provenance remains the caller's
  responsibility.
  """

  cell_index: int
  shock_boundary_points_m: tuple[Point, ...]
  centerline_boundary_points_m: tuple[Point, ...]
  cells: tuple[object, ...]
  upstream_total_pressure_Pa: tuple[float, ...] = ()
  downstream_total_pressure_Pa: tuple[float, ...] = ()
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()
  outgoing_handoff: tuple[MocChainBoundarySample, ...] = ()
  incoming_boundary_kind: MocChainBoundaryKind | None = None
  outgoing_boundary_kind: MocChainBoundaryKind | None = None
  zero_strength_shock_start_allowed: bool = False
  zero_strength_shock_endpoints_allowed: bool = False

  def __post_init__(self) -> None:
    if isinstance(self.cell_index, bool) or not isinstance(self.cell_index, int):
      raise TypeError('cell_index must be an integer')
    if self.cell_index < 1:
      raise ValueError('cell_index must be positive')
    object.__setattr__(
      self,
      'shock_boundary_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.shock_boundary_points_m),
    )
    object.__setattr__(
      self,
      'centerline_boundary_points_m',
      tuple((float(point[0]), float(point[1])) for point in self.centerline_boundary_points_m),
    )
    object.__setattr__(self, 'cells', tuple(self.cells))
    object.__setattr__(
      self,
      'upstream_total_pressure_Pa',
      tuple(float(value) for value in self.upstream_total_pressure_Pa),
    )
    object.__setattr__(
      self,
      'downstream_total_pressure_Pa',
      tuple(float(value) for value in self.downstream_total_pressure_Pa),
    )
    for name in ('incoming_handoff', 'outgoing_handoff'):
      try:
        handoff = tuple(getattr(self, name))
      except TypeError as error:
        raise TypeError(
          f'{name} must be an iterable of MocChainBoundarySample values'
        ) from error
      if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
        raise TypeError(
          f'{name} must contain MocChainBoundarySample values'
        )
      if handoff and len(handoff) < 3:
        raise ValueError(
          f'{name} must contain at least three samples when supplied'
        )
      object.__setattr__(self, name, handoff)
    for name in ('incoming_boundary_kind', 'outgoing_boundary_kind'):
      kind = getattr(self, name)
      if kind is not None and not isinstance(kind, MocChainBoundaryKind):
        raise TypeError(
          f'{name} must be a MocChainBoundaryKind or None'
        )
    for name in (
      'zero_strength_shock_start_allowed',
      'zero_strength_shock_endpoints_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellMeasurement:
  """Geometry and optional shock-loss measurements for one MOC cell."""

  status: MocShockCellMeasurementStatus
  operator_id: str
  cell_index: int
  cell_count: int
  topology: MocTopologyResult
  shock_boundary_point_count: int
  centerline_boundary_point_count: int
  shock_start_m: Point | None
  shock_end_m: Point | None
  centerline_end_m: Point | None
  axial_extent_m: tuple[float, float] | None
  axial_length_m: float | None
  shock_boundary_length_m: float | None
  centerline_boundary_length_m: float | None
  maximum_radius_m: float | None
  mesh_area_m2: float | None
  perimeter_area_m2: float | None
  area_closure_residual_m2: float | None
  pressure_sample_count: int
  minimum_total_pressure_ratio: float | None
  maximum_total_pressure_ratio: float | None
  pressure_loss_verified: bool | None
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocShockCellMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'cell_index': self.cell_index,
      'cell_count': self.cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'boundary_point_counts': {
        'shock': self.shock_boundary_point_count,
        'centerline': self.centerline_boundary_point_count,
      },
      'shock_start_m': self.shock_start_m,
      'shock_end_m': self.shock_end_m,
      'centerline_end_m': self.centerline_end_m,
      'axial_extent_m': self.axial_extent_m,
      'axial_length_m': self.axial_length_m,
      'shock_boundary_length_m': self.shock_boundary_length_m,
      'centerline_boundary_length_m': self.centerline_boundary_length_m,
      'maximum_radius_m': self.maximum_radius_m,
      'mesh_area_m2': self.mesh_area_m2,
      'perimeter_area_m2': self.perimeter_area_m2,
      'area_closure_residual_m2': self.area_closure_residual_m2,
      'pressure': {
        'sample_count': self.pressure_sample_count,
        'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
        'maximum_total_pressure_ratio': self.maximum_total_pressure_ratio,
        'pressure_loss_verified': self.pressure_loss_verified,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellChainMeasurement:
  """Independent measurements for an ordered continued-cell chain."""

  status: MocShockCellMeasurementStatus
  operator_id: str
  cells: tuple[MocShockCellMeasurement, ...]
  axial_extent_m: tuple[float, float] | None
  shock_start_spacing_m: tuple[float, ...]
  total_mesh_area_m2: float | None
  claim_status: str
  message: str
  handoff_link_count: int = 0
  handoff_links_verified: bool | None = None
  fresh_domain_verified: bool | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocShockCellMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible chain measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'cell_count': len(self.cells),
      'cells': [cell.as_report() for cell in self.cells],
      'axial_extent_m': self.axial_extent_m,
      'shock_start_spacing_m': list(self.shock_start_spacing_m),
      'total_mesh_area_m2': self.total_mesh_area_m2,
      'handoff': {
        'link_count': self.handoff_link_count,
        'links_verified': self.handoff_links_verified,
      },
      'fresh_domain_verified': self.fresh_domain_verified,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocPhysicalFieldChainMeasurementStatus(str, Enum):
  """Outcome of independently auditing a carried physical-field chain."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'field_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
  BOUNDARY_FAILURE = 'boundary_failure'
  HANDOFF_FAILURE = 'handoff_failure'
  DOMAIN_FAILURE = 'domain_failure'
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldChainMeasurement:
  """Independent evidence for a sequence of ambient-closed MOC fields.

  The measurement consumes the solver-returned fields as immutable data.  It
  rechecks each field's explicit shock/ambient/centerline perimeter, retained
  state samples, characteristic residuals, total-pressure loss, and mesh
  topology.  Adjacent fields must carry the exact centerline handoff and begin
  at a fresh downstream ambient interface.  A passing result is local
  research evidence only: canonical reflected free-boundary closure,
  refinement, and external validation still control product promotion.
  """

  status: MocPhysicalFieldChainMeasurementStatus
  operator_id: str = MOC_AMBIENT_CLOSED_PHYSICAL_FIELD_CHAIN_OPERATOR_ID
  field_count: int = 0
  field_measurements: tuple[MocShockCellMeasurement, ...] = ()
  field_statuses: tuple[str, ...] = ()
  field_topology_verified: tuple[bool, ...] = ()
  field_ambient_boundary_verified: tuple[bool, ...] = ()
  field_state_sampling_verified: tuple[bool, ...] = ()
  field_upstream_shock_coupling_verified: tuple[bool, ...] = ()
  field_physical_closure_verified: tuple[bool, ...] = ()
  handoff_link_count: int = 0
  handoff_links_verified: bool | None = None
  fresh_domain_verified: bool = False
  intercell_bridge_count: int = 0
  intercell_bridge_endpoints_m: tuple[tuple[Point, Point], ...] = ()
  intercell_bridges_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = (
    'independent-ambient-closed-physical-field-chain-audit; not-accepted'
  )
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.field_count, bool)
      or not isinstance(self.field_count, int)
      or self.field_count < 0
    ):
      raise ValueError('field_count must be a nonnegative integer')
    measurements = tuple(self.field_measurements)
    if any(
      not isinstance(measurement, MocShockCellMeasurement)
      for measurement in measurements
    ):
      raise TypeError(
        'field_measurements must contain MocShockCellMeasurement values'
      )
    if len(measurements) > self.field_count:
      raise ValueError('field_measurements cannot exceed field_count')
    object.__setattr__(self, 'field_measurements', measurements)
    statuses = tuple(str(status) for status in self.field_statuses)
    if len(statuses) > self.field_count:
      raise ValueError('field_statuses cannot exceed field_count')
    if any(not status for status in statuses):
      raise ValueError('field_statuses must contain non-empty strings')
    object.__setattr__(self, 'field_statuses', statuses)
    for name in (
      'field_topology_verified',
      'field_ambient_boundary_verified',
      'field_state_sampling_verified',
      'field_upstream_shock_coupling_verified',
      'field_physical_closure_verified',
    ):
      values = tuple(getattr(self, name))
      if len(values) > self.field_count:
        raise ValueError(f'{name} cannot exceed field_count')
      if any(not isinstance(value, bool) for value in values):
        raise TypeError(f'{name} must contain bool values')
      object.__setattr__(self, name, values)
    if (
      isinstance(self.handoff_link_count, bool)
      or not isinstance(self.handoff_link_count, int)
      or self.handoff_link_count < 0
    ):
      raise ValueError('handoff_link_count must be a nonnegative integer')
    if self.handoff_links_verified is not None and not isinstance(
      self.handoff_links_verified,
      bool,
    ):
      raise TypeError('handoff_links_verified must be a bool or None')
    if (
      isinstance(self.intercell_bridge_count, bool)
      or not isinstance(self.intercell_bridge_count, int)
      or self.intercell_bridge_count < 0
    ):
      raise ValueError('intercell_bridge_count must be a nonnegative integer')
    bridge_endpoints = tuple(self.intercell_bridge_endpoints_m)
    if len(bridge_endpoints) > self.intercell_bridge_count:
      raise ValueError(
        'intercell_bridge_endpoints_m cannot exceed intercell_bridge_count'
      )
    normalized_bridge_endpoints: list[tuple[Point, Point]] = []
    for endpoints in bridge_endpoints:
      if len(endpoints) != 2:
        raise ValueError(
          'intercell_bridge_endpoints_m must contain (start, end) pairs'
        )
      start, end = endpoints
      start_point = (float(start[0]), float(start[1]))
      end_point = (float(end[0]), float(end[1]))
      if not all(isfinite(value) for value in (*start_point, *end_point)):
        raise ValueError(
          'intercell_bridge_endpoints_m must contain finite coordinates'
        )
      normalized_bridge_endpoints.append((start_point, end_point))
    object.__setattr__(
      self,
      'intercell_bridge_endpoints_m',
      tuple(normalized_bridge_endpoints),
    )
    for name in (
      'fresh_domain_verified',
      'intercell_bridges_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocPhysicalFieldChainMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return JSON-compatible per-field and chain audit evidence."""

    audited_count = max(
      len(self.field_measurements),
      len(self.field_statuses),
      len(self.field_topology_verified),
      len(self.field_ambient_boundary_verified),
      len(self.field_state_sampling_verified),
      len(self.field_upstream_shock_coupling_verified),
      len(self.field_physical_closure_verified),
    )
    fields = []
    for index in range(audited_count):
      measurement = (
        self.field_measurements[index]
        if index < len(self.field_measurements) else None
      )
      fields.append({
        'field_index': index + 1,
        'solver_status': (
          self.field_statuses[index]
          if index < len(self.field_statuses) else None
        ),
        'topology_verified': (
          self.field_topology_verified[index]
          if index < len(self.field_topology_verified) else False
        ),
        'ambient_boundary_verified': (
          self.field_ambient_boundary_verified[index]
          if index < len(self.field_ambient_boundary_verified) else False
        ),
        'state_sampling_verified': (
          self.field_state_sampling_verified[index]
          if index < len(self.field_state_sampling_verified) else False
        ),
        'upstream_shock_coupling_verified': (
          self.field_upstream_shock_coupling_verified[index]
          if index < len(self.field_upstream_shock_coupling_verified) else False
        ),
        'physical_closure_verified': (
          self.field_physical_closure_verified[index]
          if index < len(self.field_physical_closure_verified) else False
        ),
        'measurement': None if measurement is None else measurement.as_report(),
      })
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'field_count': self.field_count,
      'audited_field_count': audited_count,
      'fields': fields,
      'handoff': {
        'link_count': self.handoff_link_count,
        'links_verified': self.handoff_links_verified,
      },
      'intercell_bridges': {
        'count': self.intercell_bridge_count,
        'verified': self.intercell_bridges_verified,
        'endpoints_m': [
          [list(start), list(end)]
          for start, end in self.intercell_bridge_endpoints_m
        ],
      },
      'fresh_domain_verified': self.fresh_domain_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus(str, Enum):
  """Outcome of independently auditing a continued alternating-source chain."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'source_failure'
  FIELD_FAILURE = 'field_failure'
  HANDOFF_FAILURE = 'handoff_failure'
  DOMAIN_FAILURE = 'domain_failure'
  SOURCE_FRESHNESS_FAILURE = 'source_freshness_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingPhysicalFieldChainMeasurement:
  """Independent evidence for a sequence of alternating physical fields.

  Each result is measured with the single-cell alternating-source operator,
  then the retained physical fields are audited as one exact ambient-closed
  chain.  The source geometry is fingerprinted independently of the incoming
  handoff so a copied source band cannot pass merely because a new wrapper or
  handoff was attached to it.  This remains research evidence: the local
  compression envelope and canonical downstream free boundary are separate
  gates.
  """

  status: MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_OPERATOR_ID
  )
  field_count: int = 0
  field_measurements: tuple[
    MocReflectedDomainAlternatingPhysicalFieldMeasurement, ...
  ] = ()
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None
  source_geometry_fingerprints: tuple[str, ...] = ()
  source_geometry_freshness_verified: bool = False
  handoff_link_count: int = 0
  handoff_links_verified: bool | None = None
  fresh_domain_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = (
    'independent-alternating-physical-field-chain-audit; not-accepted'
  )
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.field_count, bool)
      or not isinstance(self.field_count, int)
      or self.field_count < 0
    ):
      raise ValueError('field_count must be a nonnegative integer')
    measurements = tuple(self.field_measurements)
    if len(measurements) > self.field_count:
      raise ValueError('field_measurements cannot exceed field_count')
    if any(
      not isinstance(
        measurement,
        MocReflectedDomainAlternatingPhysicalFieldMeasurement,
      )
      for measurement in measurements
    ):
      raise TypeError(
        'field_measurements must contain '
        'MocReflectedDomainAlternatingPhysicalFieldMeasurement values'
      )
    object.__setattr__(self, 'field_measurements', measurements)
    fingerprints = tuple(str(value) for value in self.source_geometry_fingerprints)
    if len(fingerprints) > self.field_count:
      raise ValueError('source_geometry_fingerprints cannot exceed field_count')
    if any(not value for value in fingerprints):
      raise ValueError('source_geometry_fingerprints must be non-empty')
    object.__setattr__(self, 'source_geometry_fingerprints', fingerprints)
    if (
      isinstance(self.handoff_link_count, bool)
      or not isinstance(self.handoff_link_count, int)
      or self.handoff_link_count < 0
    ):
      raise ValueError('handoff_link_count must be a nonnegative integer')
    if self.handoff_links_verified is not None and not isinstance(
      self.handoff_links_verified,
      bool,
    ):
      raise TypeError('handoff_links_verified must be a bool or None')
    for name in (
      'source_geometry_freshness_verified',
      'fresh_domain_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_field_chain_measurement is not None and not isinstance(
      self.physical_field_chain_measurement,
      MocPhysicalFieldChainMeasurement,
    ):
      raise TypeError(
        'physical_field_chain_measurement must be a '
        'MocPhysicalFieldChainMeasurement or None'
      )
  ####

  @property
  def converged(self) -> bool:
    return (
      self.status
      is MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.CONVERGED
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'field_count': self.field_count,
      'fields': [measurement.as_report() for measurement in self.field_measurements],
      'physical_field_chain_measurement': (
        None
        if self.physical_field_chain_measurement is None
        else self.physical_field_chain_measurement.as_report()
      ),
      'source_geometry_fingerprints': list(self.source_geometry_fingerprints),
      'checks': {
        'source_geometry_freshness_verified': (
          self.source_geometry_freshness_verified
        ),
        'handoff_links_verified': self.handoff_links_verified,
        'fresh_domain_verified': self.fresh_domain_verified,
        'physical_closure_verified': self.physical_closure_verified,
      },
      'handoff': {
        'link_count': self.handoff_link_count,
        'links_verified': self.handoff_links_verified,
      },
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


class MocShockCellChainRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing independently measured chain resolutions."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'resolution_failure'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
####


@dataclass(frozen=True, slots=True)
class MocShockCellChainRefinementCase:
  """One ordered chain observation at a declared numerical resolution.

  The resolution is metadata supplied by the caller (for example, the
  number of shock samples).  The operator requires cases to be supplied from
  coarse to fine; it never infers resolution from the number of cells or
  from a geometry trace.  Optional termination metadata lets a planner audit
  whether the same typed endpoint survives refinement without treating that
  endpoint as physical termination.
  """

  resolution: int
  observations: tuple[MocShockCellObservation, ...]
  termination_reason: str | None = None
  physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 1
    ):
      raise ValueError('resolution must be a positive integer')
    try:
      observations = tuple(self.observations)
    except TypeError as error:
      raise TypeError(
        'observations must contain MocShockCellObservation values'
      ) from error
    if not observations or any(
      not isinstance(observation, MocShockCellObservation)
      for observation in observations
    ):
      raise TypeError(
        'observations must contain at least one MocShockCellObservation value'
      )
    object.__setattr__(self, 'observations', observations)
    reason = self.termination_reason
    if reason is not None:
      if isinstance(reason, Enum):
        reason = reason.value
      reason = str(reason)
      if not reason:
        raise ValueError('termination_reason must be non-empty when supplied')
      object.__setattr__(self, 'termination_reason', reason)
    if self.physical_termination is not None and not isinstance(
      self.physical_termination,
      bool,
    ):
      raise TypeError('physical_termination must be a bool or None')
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellChainRefinementMeasurement:
  """Independent numerical-sensitivity evidence for a continued chain.

  This operator compares already returned chain observations.  It does not
  solve, smooth, interpolate, or repair them.  A passing result means that
  the measured geometry and declared typed endpoint are stable over the
  supplied resolutions; it remains ``not_accepted`` evidence until the
  physical reflected-field, downstream-boundary, and external-validation
  gates are complete.
  """

  status: MocShockCellChainRefinementMeasurementStatus
  operator_id: str = MOC_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID
  cases: tuple[MocShockCellChainRefinementCase, ...] = ()
  chain_measurements: tuple[MocShockCellChainMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  cell_count: int | None = None
  resolution_order_verified: bool = False
  cell_count_consistent: bool = False
  geometry_shape_verified: bool = False
  pressure_loss_verified: bool = False
  handoff_metadata_complete: bool = False
  handoff_links_verified: bool | None = None
  termination_sensitivity_verified: bool | None = None
  axial_extent_residuals_m: tuple[float, ...] = ()
  shock_spacing_residuals_m: tuple[float, ...] = ()
  mesh_area_residuals_m2: tuple[float, ...] = ()
  refinement_convergence_verified: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    measurements = tuple(self.chain_measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and chain_measurements must have equal lengths')
    if any(not isinstance(case, MocShockCellChainRefinementCase) for case in cases):
      raise TypeError('cases must contain MocShockCellChainRefinementCase values')
    if any(
      not isinstance(measurement, MocShockCellChainMeasurement)
      for measurement in measurements
    ):
      raise TypeError(
        'chain_measurements must contain MocShockCellChainMeasurement values'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'chain_measurements', measurements)
    object.__setattr__(
      self,
      'resolutions',
      tuple(case.resolution for case in cases),
    )
    for name in (
      'axial_extent_residuals_m',
      'shock_spacing_residuals_m',
      'mesh_area_residuals_m2',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    if self.cell_count is not None:
      if isinstance(self.cell_count, bool) or self.cell_count < 1:
        raise ValueError('cell_count must be positive when supplied')
    for name in (
      'resolution_order_verified',
      'cell_count_consistent',
      'geometry_shape_verified',
      'pressure_loss_verified',
      'handoff_metadata_complete',
      'refinement_convergence_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in ('handoff_links_verified', 'termination_sensitivity_verified'):
      value = getattr(self, name)
      if value is not None and not isinstance(value, bool):
        raise TypeError(f'{name} must be a bool or None')
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocShockCellChainRefinementMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return JSON-compatible refinement evidence."""

    case_reports = []
    for case, measurement in zip(
      self.cases,
      self.chain_measurements,
      strict=True,
    ):
      case_reports.append({
        'resolution': case.resolution,
        'termination_reason': case.termination_reason,
        'physical_termination': case.physical_termination,
        'measurement': measurement.as_report(),
      })
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'resolutions': list(self.resolutions),
      'cell_count': self.cell_count,
      'cases': case_reports,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'cell_count_consistent': self.cell_count_consistent,
        'geometry_shape_verified': self.geometry_shape_verified,
        'pressure_loss_verified': self.pressure_loss_verified,
        'handoff_metadata_complete': self.handoff_metadata_complete,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_sensitivity_verified': self.termination_sensitivity_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
      },
      'residuals': {
        'axial_extent_residuals_m': list(self.axial_extent_residuals_m),
        'shock_spacing_residuals_m': list(self.shock_spacing_residuals_m),
        'mesh_area_residuals_m2': list(self.mesh_area_residuals_m2),
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _chain_refinement_failure(
  status: MocShockCellChainRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocShockCellChainRefinementCase] = (),
  chain_measurements: Sequence[MocShockCellChainMeasurement] = (),
  resolution_order_verified: bool = False,
  cell_count_consistent: bool = False,
  geometry_shape_verified: bool = False,
  pressure_loss_verified: bool = False,
  handoff_metadata_complete: bool = False,
  handoff_links_verified: bool | None = None,
  termination_sensitivity_verified: bool | None = None,
  axial_extent_residuals_m: Sequence[float] = (),
  shock_spacing_residuals_m: Sequence[float] = (),
  mesh_area_residuals_m2: Sequence[float] = (),
  refinement_convergence_verified: bool = False,
) -> MocShockCellChainRefinementMeasurement:
  valid_cases = tuple(
    case for case in cases if isinstance(case, MocShockCellChainRefinementCase)
  )
  valid_measurements = tuple(
    measurement
    for measurement in chain_measurements
    if isinstance(measurement, MocShockCellChainMeasurement)
  )
  paired_count = min(len(valid_cases), len(valid_measurements))
  return MocShockCellChainRefinementMeasurement(
    status=status,
    cases=valid_cases[:paired_count],
    chain_measurements=valid_measurements[:paired_count],
    resolution_order_verified=resolution_order_verified,
    cell_count_consistent=cell_count_consistent,
    geometry_shape_verified=geometry_shape_verified,
    pressure_loss_verified=pressure_loss_verified,
    handoff_metadata_complete=handoff_metadata_complete,
    handoff_links_verified=handoff_links_verified,
    termination_sensitivity_verified=termination_sensitivity_verified,
    axial_extent_residuals_m=tuple(axial_extent_residuals_m),
    shock_spacing_residuals_m=tuple(shock_spacing_residuals_m),
    mesh_area_residuals_m2=tuple(mesh_area_residuals_m2),
    refinement_convergence_verified=refinement_convergence_verified,
    message=message,
  )
####


def measure_moc_shock_cell_chain_refinement(
  cases: Sequence[MocShockCellChainRefinementCase],
  *,
  endpoint_tolerance_m: float = 2.0e-5,
  shock_spacing_tolerance_m: float = 1.0e-6,
  area_tolerance_m2: float = 2.0e-4,
  position_tolerance_m: float = 1.0e-10,
  axis_tolerance_m: float = 1.0e-10,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocShockCellChainRefinementMeasurement:
  """Compare independent chain geometry over increasing resolutions.

  The operator reruns :func:`measure_moc_shock_cell_chain` for each supplied
  data case and compares only returned measurements.  It requires stable
  cell count and per-cell spacing shape, strict resolution ordering, strict
  shock total-pressure loss, and bounded changes in chain extent, shock
  spacing, and measured mesh area.  Optional planner termination metadata is
  checked when supplied for every case.
  """

  for name, value in (
    ('endpoint_tolerance_m', endpoint_tolerance_m),
    ('shock_spacing_tolerance_m', shock_spacing_tolerance_m),
    ('area_tolerance_m2', area_tolerance_m2),
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    items = tuple(cases)
  except TypeError:
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  if len(items) < 2:
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.INVALID_INPUT,
      'at least two chain refinement cases are required',
    )
  if any(not isinstance(case, MocShockCellChainRefinementCase) for case in items):
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain MocShockCellChainRefinementCase values',
      cases=items,
    )
  resolutions = tuple(case.resolution for case in items)
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
      cases=items,
    )
  measurements = tuple(
    measure_moc_shock_cell_chain(
      case.observations,
      position_tolerance_m=position_tolerance_m,
      axis_tolerance_m=axis_tolerance_m,
      area_tolerance_m2=area_tolerance_m2,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for case in items
  )
  if any(not measurement.converged for measurement in measurements):
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.CASE_FAILURE,
      'one or more refinement cases failed independent chain measurement',
      cases=items,
      chain_measurements=measurements,
      resolution_order_verified=True,
    )
  counts = tuple(len(measurement.cells) for measurement in measurements)
  cell_count_consistent = len(set(counts)) == 1 and counts[0] > 0
  spacing_shapes = tuple(
    len(measurement.shock_start_spacing_m) for measurement in measurements
  )
  geometry_shape_verified = len(set(spacing_shapes)) == 1
  if not cell_count_consistent or not geometry_shape_verified:
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'refinement cases must retain the same cell count and shock-spacing shape',
      cases=items,
      chain_measurements=measurements,
      resolution_order_verified=True,
      cell_count_consistent=cell_count_consistent,
      geometry_shape_verified=geometry_shape_verified,
    )
  extents = tuple(measurement.axial_extent_m for measurement in measurements)
  if any(extent is None for extent in extents):
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.CASE_FAILURE,
      'converged refinement measurements must expose axial extents',
      cases=items,
      chain_measurements=measurements,
      resolution_order_verified=True,
      cell_count_consistent=True,
      geometry_shape_verified=True,
    )
  resolved_extents = tuple(extent for extent in extents if extent is not None)
  axial_extent_residuals = tuple(
    max(
      abs(current[0] - previous[0]),
      abs(current[1] - previous[1]),
    )
    for previous, current in zip(
      resolved_extents,
      resolved_extents[1:],
    )
  )
  shock_spacing_residuals = tuple(
    max(
      (
        abs(current - previous)
        for previous, current in zip(
          previous_measurement.shock_start_spacing_m,
          current_measurement.shock_start_spacing_m,
          strict=True,
        )
      ),
      default=0.0,
    )
    for previous_measurement, current_measurement in zip(
      measurements,
      measurements[1:],
    )
  )
  mesh_area_residuals = tuple(
    abs(current.total_mesh_area_m2 - previous.total_mesh_area_m2)
    for previous, current in zip(measurements, measurements[1:])
    if previous.total_mesh_area_m2 is not None
    and current.total_mesh_area_m2 is not None
  )
  if len(mesh_area_residuals) != len(measurements) - 1:
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.CASE_FAILURE,
      'converged refinement measurements must expose total mesh areas',
      cases=items,
      chain_measurements=measurements,
      resolution_order_verified=True,
      cell_count_consistent=True,
      geometry_shape_verified=True,
      axial_extent_residuals_m=axial_extent_residuals,
      shock_spacing_residuals_m=shock_spacing_residuals,
    )
  pressure_loss_verified = all(
    cell.pressure_loss_verified is True
    for measurement in measurements
    for cell in measurement.cells
  )
  handoff_metadata_complete = all(
    measurement.handoff_links_verified is not None
    for measurement in measurements
  )
  handoff_links_verified = (
    None
    if not any(measurement.handoff_links_verified is not None for measurement in measurements)
    else handoff_metadata_complete
    and all(measurement.handoff_links_verified is True for measurement in measurements)
  )
  termination_metadata = tuple(
    (case.termination_reason, case.physical_termination)
    for case in items
  )
  if not any(
    reason is not None or physical is not None
    for reason, physical in termination_metadata
  ):
    termination_sensitivity_verified = None
  elif any(
    reason is None or physical is None
    for reason, physical in termination_metadata
  ):
    termination_sensitivity_verified = False
  else:
    termination_sensitivity_verified = len(set(termination_metadata)) == 1
  refinement_convergence_verified = (
    all(
      residual <= float(endpoint_tolerance_m)
      for residual in axial_extent_residuals
    )
    and all(
      residual <= float(shock_spacing_tolerance_m)
      for residual in shock_spacing_residuals
    )
    and all(
      residual <= float(area_tolerance_m2)
      for residual in mesh_area_residuals
    )
  )
  if (
    not pressure_loss_verified
    or not refinement_convergence_verified
    or termination_sensitivity_verified is False
  ):
    return _chain_refinement_failure(
      MocShockCellChainRefinementMeasurementStatus.SENSITIVITY_FAILURE,
      'refinement sensitivity or pressure-loss checks exceeded the declared tolerances',
      cases=items,
      chain_measurements=measurements,
      resolution_order_verified=True,
      cell_count_consistent=True,
      geometry_shape_verified=True,
      pressure_loss_verified=pressure_loss_verified,
      handoff_metadata_complete=handoff_metadata_complete,
      handoff_links_verified=handoff_links_verified,
      termination_sensitivity_verified=termination_sensitivity_verified,
      axial_extent_residuals_m=axial_extent_residuals,
      shock_spacing_residuals_m=shock_spacing_residuals,
      mesh_area_residuals_m2=mesh_area_residuals,
      refinement_convergence_verified=refinement_convergence_verified,
    )
  return MocShockCellChainRefinementMeasurement(
    status=MocShockCellChainRefinementMeasurementStatus.CONVERGED,
    cases=items,
    chain_measurements=measurements,
    cell_count=counts[0],
    resolution_order_verified=True,
    cell_count_consistent=True,
    geometry_shape_verified=True,
    pressure_loss_verified=True,
    handoff_metadata_complete=handoff_metadata_complete,
    handoff_links_verified=handoff_links_verified,
    termination_sensitivity_verified=termination_sensitivity_verified,
    axial_extent_residuals_m=axial_extent_residuals,
    shock_spacing_residuals_m=shock_spacing_residuals,
    mesh_area_residuals_m2=mesh_area_residuals,
    refinement_convergence_verified=True,
    message=(
      'independent continued shock-cell geometry is stable across the '
      'declared resolutions; this remains numerical research evidence and '
      'does not establish physical chain closure'
    ),
  )
####


class MocChainPlannerMeasurementStatus(str, Enum):
  """Outcome of independently auditing a continued-cell planner trace."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  STEP_FAILURE = 'step_failure'
  HANDOFF_FAILURE = 'handoff_failure'
  DOMAIN_FAILURE = 'domain_failure'
  TERMINATION_FAILURE = 'termination_failure'
  FIDELITY_FAILURE = 'fidelity_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocChainPlannerMeasurement:
  """Independent checks for a planner's continued shock-cell trace.

  The planner records its own handoff metadata while orchestrating callbacks.
  This operator recomputes the same boundaries from the returned chain and
  compares every recorded fingerprint, sequence link, result, and terminal
  decision.  It deliberately reports a research trace only: a successful
  audit does not establish a free-boundary shock solution or a product claim.
  """

  status: MocChainPlannerMeasurementStatus
  operator_id: str
  planner_kind: str | None
  chain_status: str | None
  termination_reason: str | None
  step_count: int
  chain_cell_count: int
  chain_cells_contiguous: bool
  chain_topology_verified: bool
  domain_freshness_verified: bool
  step_sequence_verified: bool
  incoming_handoffs_verified: bool
  returned_handoffs_verified: bool
  handoff_link_count: int
  handoff_links_verified: bool | None
  termination_verified: bool
  fidelity_isolation_verified: bool
  physical_termination: bool | None
  production_claim_allowed: bool
  claim_status: str
  message: str

  @property
  def converged(self) -> bool:
    return self.status is MocChainPlannerMeasurementStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible planner-trace measurement record."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'planner_kind': self.planner_kind,
      'chain_status': self.chain_status,
      'termination_reason': self.termination_reason,
      'counts': {
        'steps': self.step_count,
        'chain_cells': self.chain_cell_count,
        'handoff_links': self.handoff_link_count,
      },
      'checks': {
        'chain_cells_contiguous': self.chain_cells_contiguous,
        'chain_topology_verified': self.chain_topology_verified,
        'domain_freshness_verified': self.domain_freshness_verified,
        'step_sequence_verified': self.step_sequence_verified,
        'incoming_handoffs_verified': self.incoming_handoffs_verified,
        'returned_handoffs_verified': self.returned_handoffs_verified,
        'handoff_links_verified': self.handoff_links_verified,
        'termination_verified': self.termination_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'physical_termination': self.physical_termination,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _planner_measurement_failure(
  status: MocChainPlannerMeasurementStatus,
  message: str,
  *,
  planner_kind: str | None = None,
  chain_status: str | None = None,
  termination_reason: str | None = None,
  step_count: int = 0,
  chain_cell_count: int = 0,
  chain_cells_contiguous: bool = False,
  chain_topology_verified: bool = False,
  domain_freshness_verified: bool = False,
  step_sequence_verified: bool = False,
  incoming_handoffs_verified: bool = False,
  returned_handoffs_verified: bool = False,
  handoff_link_count: int = 0,
  handoff_links_verified: bool | None = None,
  termination_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  physical_termination: bool | None = None,
  production_claim_allowed: bool = False,
) -> MocChainPlannerMeasurement:
  return MocChainPlannerMeasurement(
    status=status,
    operator_id=MOC_CHAIN_PLANNER_OPERATOR_ID,
    planner_kind=planner_kind,
    chain_status=chain_status,
    termination_reason=termination_reason,
    step_count=step_count,
    chain_cell_count=chain_cell_count,
    chain_cells_contiguous=chain_cells_contiguous,
    chain_topology_verified=chain_topology_verified,
    domain_freshness_verified=domain_freshness_verified,
    step_sequence_verified=step_sequence_verified,
    incoming_handoffs_verified=incoming_handoffs_verified,
    returned_handoffs_verified=returned_handoffs_verified,
    handoff_link_count=handoff_link_count,
    handoff_links_verified=handoff_links_verified,
    termination_verified=termination_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_termination=physical_termination,
    production_claim_allowed=production_claim_allowed,
    claim_status='independent-planner-trace-audit; not-accepted',
    message=message,
  )
####


def _planner_handoff_fingerprint(
  boundary: tuple[MocChainBoundarySample, ...],
) -> str | None:
  """Recompute the planner's exact typed state/pressure boundary digest."""

  if not boundary:
    return None
  payload = '\n'.join(
    '|'.join(
      value.hex()
      for value in (
        sample.state.x_m,
        sample.state.y_m,
        sample.state.theta_rad,
        sample.state.mach,
        sample.state.gamma,
        sample.total_pressure_Pa,
      )
    )
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()
####


def measure_moc_chain_planner(
  planner: MocChainPlannerResult,
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocChainPlannerMeasurement:
  """Independently audit a continued-cell planner and its terminal decision.

  The operator never uses ``planner.handoff_links_verified`` as evidence.  It
  reconstructs each incoming boundary from the chain cell, recomputes outgoing
  boundary fingerprints, and checks that the final typed termination agrees
  with the chain result.  The current acceptance target is an explicit
  solver-terminated trace; a planner without a typed final decision is
  intentionally reported as an audit failure.
  """

  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isinstance(planner, MocChainPlannerResult):
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.INVALID_INPUT,
      'planner must be a MocChainPlannerResult',
    )

  raw_cells = tuple(planner.chain.cells)
  steps = tuple(planner.steps)
  planner_kind = planner.planner_kind.value
  chain_status = planner.chain.status.value
  termination_reason = planner.chain.termination_reason.value
  physical_termination = planner.chain.physical_termination
  step_count = len(steps)
  chain_cell_count = len(raw_cells)
  handoff_link_count = max(0, step_count - 1)
  common = {
    'planner_kind': planner_kind,
    'chain_status': chain_status,
    'termination_reason': termination_reason,
    'step_count': step_count,
    'chain_cell_count': chain_cell_count,
    'handoff_link_count': handoff_link_count,
    'physical_termination': physical_termination,
    'production_claim_allowed': planner.production_claim_allowed,
  }

  if not raw_cells or not steps:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.INVALID_INPUT,
      'planner trace must contain at least one cell and one callback step',
      **common,
    )
  if any(not isinstance(cell, MocChainCell) for cell in raw_cells):
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.INVALID_INPUT,
      'planner chain must contain MocChainCell values',
      **common,
    )
  cells = tuple(cell for cell in raw_cells if isinstance(cell, MocChainCell))
  cell_indices = tuple(cell.cell_index for cell in cells)
  chain_cells_contiguous = cell_indices == tuple(range(1, chain_cell_count + 1))
  if not chain_cells_contiguous:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.STEP_FAILURE,
      'planner chain cells must have contiguous one-based indices',
      chain_cells_contiguous=False,
      **common,
    )

  chain_topology_verified = True
  for cell in cells:
    topology = validate_moc_mesh(cell.mesh)
    if not (
      topology.connected
      and topology.forms_closed_zone
      and topology.nonmanifold_edge_count == 0
    ):
      chain_topology_verified = False
      break
  if not chain_topology_verified:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.TOPOLOGY_FAILURE,
      'one or more planner cells failed the independent closed-mesh topology check',
      chain_cells_contiguous=True,
      chain_topology_verified=False,
      **common,
    )

  fidelity_isolation_verified = (
    planner.production_claim_allowed is False
    and all(
      cell.geometry_fidelity is MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
      and cell.physical_closure is MocCellClosureStatus.CLOSED
      for cell in cells
    )
  )
  if not fidelity_isolation_verified:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.FIDELITY_FAILURE,
      'planner trace contains a non-resolved or promotable cell fidelity',
      chain_cells_contiguous=True,
      chain_topology_verified=True,
      fidelity_isolation_verified=False,
      **common,
    )

  domain_freshness_verified = True
  for index, (current, next_cell) in enumerate(
        zip(cells[:-1], cells[1:], strict=True)
  ):
    if abs(next_cell.start_x_m - current.end_x_m) > position_tolerance_m:
      domain_freshness_verified = False
      domain_message = (
        f'planner cell boundary {index + 1}->{index + 2} is not axially '
        'contiguous'
      )
      break
    mesh_extent = next_cell.mesh_x_extent_m
    if mesh_extent is None:
      domain_freshness_verified = False
      domain_message = f'planner cell {index + 2} does not expose finite mesh x extent'
      break
    if mesh_extent[0] < current.end_x_m - position_tolerance_m:
      domain_freshness_verified = False
      domain_message = (
        f'planner cell {index + 2} mesh reuses an upstream domain: '
        f'minimum_x={mesh_extent[0]}, current_end_x={current.end_x_m}'
      )
      break
    if mesh_extent[1] <= current.end_x_m + position_tolerance_m:
      domain_freshness_verified = False
      domain_message = (
        f'planner cell {index + 2} mesh has no downstream progress: '
        f'maximum_x={mesh_extent[1]}, current_end_x={current.end_x_m}'
      )
      break
    boundary_extent = next_cell.continuation_boundary_x_extent_m
    if boundary_extent is not None and (
      boundary_extent[0] < current.end_x_m - position_tolerance_m
    ):
      domain_freshness_verified = False
      domain_message = (
        f'planner cell {index + 2} carried boundary reuses an upstream '
        f'domain: minimum_x={boundary_extent[0]}, '
        f'current_end_x={current.end_x_m}'
      )
      break
  if not domain_freshness_verified:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.DOMAIN_FAILURE,
      domain_message,
      chain_cells_contiguous=True,
      chain_topology_verified=True,
      domain_freshness_verified=False,
      fidelity_isolation_verified=True,
      **common,
    )

  expected_current_indices = tuple(range(1, chain_cell_count + 1))
  expected_next_indices = tuple(range(2, chain_cell_count + 2))
  step_sequence_verified = (
    tuple(step.current_cell_index for step in steps) == expected_current_indices
    and tuple(step.next_cell_index for step in steps) == expected_next_indices
  )
  if not step_sequence_verified:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.STEP_FAILURE,
      'planner steps must visit every carried cell and attempt the next index in order',
      chain_cells_contiguous=True,
      chain_topology_verified=True,
      domain_freshness_verified=True,
      step_sequence_verified=False,
      fidelity_isolation_verified=True,
      **common,
    )

  returned_handoffs_verified = True
  previous_returned_fingerprint: str | None = None
  for index, step in enumerate(steps):
    current = cells[index]
    boundary = current.continuation_boundary
    expected_fingerprint = _planner_handoff_fingerprint(boundary)
    expected_pressure_range = (
      None
      if not boundary
      else (
        min(sample.total_pressure_Pa for sample in boundary),
        max(sample.total_pressure_Pa for sample in boundary),
      )
    )
    if (
      not boundary
      or abs(step.current_end_x_m - current.end_x_m) > position_tolerance_m
      or step.boundary_kind is not current.continuation_boundary_kind
      or step.incoming_handoff_sample_count != len(boundary)
      or step.incoming_total_pressure_range_Pa != expected_pressure_range
      or step.incoming_handoff_fingerprint != expected_fingerprint
    ):
      return _planner_measurement_failure(
        MocChainPlannerMeasurementStatus.HANDOFF_FAILURE,
        f'planner step {index + 1} does not reproduce its current-cell handoff',
        chain_cells_contiguous=True,
        chain_topology_verified=True,
        domain_freshness_verified=True,
        step_sequence_verified=True,
        incoming_handoffs_verified=False,
        returned_handoffs_verified=returned_handoffs_verified,
        fidelity_isolation_verified=True,
        **common,
      )
    expected_link_verified = (
      step.incoming_handoff_link_verified is None
      if index == 0
      else (
        previous_returned_fingerprint is not None
        and expected_fingerprint == previous_returned_fingerprint
        and step.incoming_handoff_link_verified is True
      )
    )
    if not expected_link_verified:
      return _planner_measurement_failure(
        MocChainPlannerMeasurementStatus.HANDOFF_FAILURE,
        f'planner handoff link {index} is not an exact returned-to-incoming match',
        chain_cells_contiguous=True,
        chain_topology_verified=True,
        domain_freshness_verified=True,
        step_sequence_verified=True,
        incoming_handoffs_verified=False,
        returned_handoffs_verified=returned_handoffs_verified,
        fidelity_isolation_verified=True,
        **common,
      )

    if step.result_kind in (
      'field-solve-returned',
      'physical-field-solve-returned',
      'cell-returned',
    ):
      if step.next_cell_index > chain_cell_count:
        returned_handoffs_verified = False
        return _planner_measurement_failure(
          MocChainPlannerMeasurementStatus.STEP_FAILURE,
          f'planner step {index + 1} returned a cell outside the chain result',
          chain_cells_contiguous=True,
          chain_topology_verified=True,
          domain_freshness_verified=True,
          step_sequence_verified=True,
          incoming_handoffs_verified=True,
          returned_handoffs_verified=False,
          fidelity_isolation_verified=True,
          **common,
        )
      if step.result_kind in (
        'field-solve-returned',
        'physical-field-solve-returned',
      ) and (
        step.result_consumed_handoff_sample_count != len(boundary)
        or step.result_consumed_total_pressure_range_Pa != expected_pressure_range
        or step.result_consumed_handoff_fingerprint != expected_fingerprint
      ):
        returned_handoffs_verified = False
        return _planner_measurement_failure(
          MocChainPlannerMeasurementStatus.HANDOFF_FAILURE,
          f'planner step {index + 1} does not reproduce the handoff consumed by its returned field',
          chain_cells_contiguous=True,
          chain_topology_verified=True,
          domain_freshness_verified=True,
          step_sequence_verified=True,
          incoming_handoffs_verified=True,
          returned_handoffs_verified=False,
          fidelity_isolation_verified=True,
          **common,
        )
      next_cell = cells[step.next_cell_index - 1]
      next_boundary = next_cell.continuation_boundary
      next_fingerprint = _planner_handoff_fingerprint(next_boundary)
      next_pressure_range = (
        None
        if not next_boundary
        else (
          min(sample.total_pressure_Pa for sample in next_boundary),
          max(sample.total_pressure_Pa for sample in next_boundary),
        )
      )
      if (
        abs(next_cell.start_x_m - current.end_x_m) > position_tolerance_m
        or step.result_end_x_m is None
        or abs(step.result_end_x_m - next_cell.end_x_m) > position_tolerance_m
        or step.result_geometry_fidelity is not next_cell.geometry_fidelity
        or step.result_physical_closure is not next_cell.physical_closure
        or step.result_boundary_kind is not next_cell.continuation_boundary_kind
        or step.result_handoff_sample_count != len(next_boundary)
        or step.result_total_pressure_range_Pa != next_pressure_range
        or step.result_handoff_fingerprint != next_fingerprint
      ):
        returned_handoffs_verified = False
        return _planner_measurement_failure(
          MocChainPlannerMeasurementStatus.HANDOFF_FAILURE,
          f'planner step {index + 1} does not reproduce its returned-cell handoff',
          chain_cells_contiguous=True,
          chain_topology_verified=True,
          domain_freshness_verified=True,
          step_sequence_verified=True,
          incoming_handoffs_verified=True,
          returned_handoffs_verified=False,
          fidelity_isolation_verified=True,
          **common,
        )
      previous_returned_fingerprint = next_fingerprint
      continue

    if step.result_kind in ('termination-returned', 'no-cell-returned'):
      if (
        step.result_end_x_m is not None
        or step.result_geometry_fidelity is not None
        or step.result_physical_closure is not None
        or step.result_boundary_kind is not None
        or step.result_handoff_sample_count is not None
        or step.result_total_pressure_range_Pa is not None
        or step.result_handoff_fingerprint is not None
        or step.result_consumed_handoff_sample_count is not None
        or step.result_consumed_total_pressure_range_Pa is not None
        or step.result_consumed_handoff_fingerprint is not None
      ):
        return _planner_measurement_failure(
          MocChainPlannerMeasurementStatus.TERMINATION_FAILURE,
          f'planner step {index + 1} attaches a cell handoff to a termination',
          chain_cells_contiguous=True,
          chain_topology_verified=True,
          domain_freshness_verified=True,
          step_sequence_verified=True,
          incoming_handoffs_verified=True,
          returned_handoffs_verified=returned_handoffs_verified,
          fidelity_isolation_verified=True,
          **common,
        )
      previous_returned_fingerprint = None
      continue

    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.STEP_FAILURE,
      f'planner step {index + 1} has unsupported result kind {step.result_kind!r}',
      chain_cells_contiguous=True,
      chain_topology_verified=True,
      domain_freshness_verified=True,
      step_sequence_verified=True,
      incoming_handoffs_verified=True,
      returned_handoffs_verified=False,
      fidelity_isolation_verified=True,
      **common,
    )

  last_step = steps[-1]
  termination_verified = False
  if last_step.result_kind == 'termination-returned':
    termination_verified = (
      last_step.result_termination_reason is planner.chain.termination_reason
      and last_step.result_physical_termination is physical_termination
    )
  elif last_step.result_kind == 'no-cell-returned':
    termination_verified = (
      planner.chain.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
      and physical_termination is False
    )
  if not termination_verified:
    return _planner_measurement_failure(
      MocChainPlannerMeasurementStatus.TERMINATION_FAILURE,
      'planner final step does not match the chain termination decision',
      chain_cells_contiguous=True,
      chain_topology_verified=True,
      domain_freshness_verified=True,
      step_sequence_verified=True,
      incoming_handoffs_verified=True,
      returned_handoffs_verified=returned_handoffs_verified,
      handoff_links_verified=(
        None if handoff_link_count == 0 else returned_handoffs_verified
      ),
      termination_verified=False,
      fidelity_isolation_verified=True,
      **common,
    )

  return MocChainPlannerMeasurement(
    status=MocChainPlannerMeasurementStatus.CONVERGED,
    operator_id=MOC_CHAIN_PLANNER_OPERATOR_ID,
    planner_kind=planner_kind,
    chain_status=chain_status,
    termination_reason=termination_reason,
    step_count=step_count,
    chain_cell_count=chain_cell_count,
    chain_cells_contiguous=True,
    chain_topology_verified=True,
    domain_freshness_verified=True,
    step_sequence_verified=True,
    incoming_handoffs_verified=True,
    returned_handoffs_verified=returned_handoffs_verified,
    handoff_link_count=handoff_link_count,
    handoff_links_verified=(
      None if handoff_link_count == 0 else returned_handoffs_verified
    ),
    termination_verified=True,
    fidelity_isolation_verified=True,
    physical_termination=physical_termination,
    production_claim_allowed=planner.production_claim_allowed,
    claim_status='independent-planner-trace-audit; not-accepted',
    message=(
      'planner cell sequence, exact state/pressure handoffs, typed solver '
      'termination, and fidelity isolation independently verified; physical '
      'free-boundary closure remains unestablished'
    ),
  )
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _failure(
  status: MocShockCellMeasurementStatus,
  *,
  cell_index: int,
  cell_count: int,
  shock_boundary_point_count: int,
  centerline_boundary_point_count: int,
  topology: MocTopologyResult | None = None,
  message: str,
) -> MocShockCellMeasurement:
  return MocShockCellMeasurement(
    status=status,
    operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
    cell_index=cell_index,
    cell_count=cell_count,
    topology=_empty_topology() if topology is None else topology,
    shock_boundary_point_count=shock_boundary_point_count,
    centerline_boundary_point_count=centerline_boundary_point_count,
    shock_start_m=None,
    shock_end_m=None,
    centerline_end_m=None,
    axial_extent_m=None,
    axial_length_m=None,
    shock_boundary_length_m=None,
    centerline_boundary_length_m=None,
    maximum_radius_m=None,
    mesh_area_m2=None,
    perimeter_area_m2=None,
    area_closure_residual_m2=None,
    pressure_sample_count=0,
    minimum_total_pressure_ratio=None,
    maximum_total_pressure_ratio=None,
    pressure_loss_verified=None,
    claim_status='not_accepted',
    message=message,
  )
####


def _points(value: Sequence[Sequence[float]], name: str) -> tuple[Point, ...]:
  points: list[Point] = []
  for index, point in enumerate(value):
    try:
      if len(point) != 2:
        raise ValueError
      candidate = (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError) as error:
      raise ValueError(f'{name} point {index} is not a pair of coordinates') from error
    if not all(isfinite(coordinate) for coordinate in candidate):
      raise ValueError(f'{name} point {index} is not finite')
    points.append(candidate)
  if len(points) < 2:
    raise ValueError(f'{name} requires at least two points')
  return tuple(points)
####


def _validate_polyline(
  points: tuple[Point, ...],
  name: str,
  *,
  position_tolerance_m: float,
  require_strict_x: bool,
) -> str | None:
  if any(point[1] < -position_tolerance_m for point in points):
    return f'{name} must remain on or above the symmetry line'
  for first, second in zip(points, points[1:]):
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    if require_strict_x and dx <= position_tolerance_m:
      return f'{name} must be strictly downstream in x'
    if not require_strict_x and dx < -position_tolerance_m:
      return f'{name} must not move upstream in x'
    if dy > position_tolerance_m:
      return f'{name} must be nonincreasing in y'
  return None
####


def _key(point: Point, tolerance_m: float) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)
####


def _edge_counts(
  cells: tuple[object, ...],
  *,
  vertex_tolerance_m: float,
) -> tuple[
  dict[tuple[tuple[int, int], tuple[int, int]], int],
  dict[tuple[int, int], Point],
]:
  counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  points: dict[tuple[int, int], Point] = {}
  for cell in cells:
    vertices = tuple(
      (float(point[0]), float(point[1]))
      for point in getattr(cell, 'vertices_xr_m')
    )
    keys = tuple(_key(point, vertex_tolerance_m) for point in vertices)
    for key, point in zip(keys, vertices, strict=True):
      points[key] = point
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge = (first, second) if first <= second else (second, first)
      counts[edge] = counts.get(edge, 0) + 1
  return counts, points
####


def _cell_vertices(cell: object) -> tuple[Point, ...]:
  raw_vertices = getattr(cell, 'vertices_xr_m', None)
  if raw_vertices is None:
    raise AttributeError('cell does not expose vertices_xr_m')
  vertices: list[Point] = []
  for index, point in enumerate(raw_vertices):
    try:
      if len(point) != 2:
        raise ValueError
      candidate = (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError) as error:
      raise ValueError(f'cell vertex {index} is not a coordinate pair') from error
    if not all(isfinite(coordinate) for coordinate in candidate):
      raise ValueError(f'cell vertex {index} is not finite')
    vertices.append(candidate)
  return tuple(vertices)
####


def _polyline_has_boundary_edges(
  polyline: tuple[Point, ...],
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  *,
  vertex_tolerance_m: float,
) -> bool:
  for first, second in zip(polyline, polyline[1:]):
    first_key = _key(first, vertex_tolerance_m)
    second_key = _key(second, vertex_tolerance_m)
    edge = (
      (first_key, second_key)
      if first_key <= second_key
      else (second_key, first_key)
    )
    if edge_counts.get(edge) != 1:
      return False
  return True
####


def _perimeter_points(
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  vertex_points: dict[tuple[int, int], Point],
) -> tuple[Point, ...] | None:
  boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
  graph: dict[tuple[int, int], list[tuple[int, int]]] = {}
  for first, second in boundary_edges:
    graph.setdefault(first, []).append(second)
    graph.setdefault(second, []).append(first)
  if not graph or any(len(neighbors) != 2 for neighbors in graph.values()):
    return None
  start = next(iter(graph))
  cycle = [start]
  previous: tuple[int, int] | None = None
  current = start
  while True:
    neighbors = graph[current]
    next_vertex = neighbors[0] if neighbors[0] != previous else neighbors[1]
    if next_vertex == start:
      break
    if next_vertex in cycle or len(cycle) > len(graph):
      return None
    cycle.append(next_vertex)
    previous, current = current, next_vertex
  if len(cycle) != len(graph):
    return None
  return tuple(vertex_points[key] for key in cycle)
####


def _polygon_area(points: Sequence[Point]) -> float:
  return 0.5 * fsum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]))
  )
####


def _pressure_metrics(
  upstream: tuple[float, ...],
  downstream: tuple[float, ...],
  *,
  expected_count: int,
  zero_strength_shock_start_allowed: bool = False,
  zero_strength_shock_endpoints_allowed: bool = False,
  zero_strength_tolerance: float = 1.0e-10,
) -> tuple[int, float | None, float | None, bool | None, str | None]:
  if not upstream and not downstream:
    return 0, None, None, None, None
  if len(upstream) != len(downstream) or len(upstream) != expected_count:
    return (
      0,
      None,
      None,
      False,
      'upstream and downstream pressure samples must both match the shock boundary',
    )
  if any(
      not isfinite(value) or value <= 0.0
      for value in (*upstream, *downstream)
  ):
    return 0, None, None, False, 'total-pressure samples must be finite and positive'
  ratios = tuple(
    downstream_value / upstream_value
    for upstream_value, downstream_value in zip(upstream, downstream, strict=True)
  )
  loss_verified = all(
    downstream_value < upstream_value
    for upstream_value, downstream_value in zip(upstream, downstream, strict=True)
  )
  if not loss_verified:
    start_allowed = bool(
      zero_strength_shock_start_allowed
      and abs(ratios[0] - 1.0) <= zero_strength_tolerance
      and all(0.0 < ratio < 1.0 for ratio in ratios[1:])
    )
    endpoints_allowed = bool(
      zero_strength_shock_endpoints_allowed
      and abs(ratios[0] - 1.0) <= zero_strength_tolerance
      and abs(ratios[-1] - 1.0) <= zero_strength_tolerance
      and all(0.0 < ratio < 1.0 for ratio in ratios[1:-1])
    )
    loss_verified = start_allowed or endpoints_allowed
  return (
    len(ratios),
    min(ratios),
    max(ratios),
    loss_verified,
    None if loss_verified else (
      'every shock sample must reduce total pressure unless an explicit '
      'zero-strength endpoint allowance is supplied'
    ),
  )
####


def measure_moc_shock_cell(
  observation: MocShockCellObservation,
  *,
  position_tolerance_m: float = 1.0e-10,
  axis_tolerance_m: float = 1.0e-10,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocShockCellMeasurement:
  """Measure one shock-cell field without inferring missing physical edges."""

  if not isinstance(observation, MocShockCellObservation):
    raise TypeError('observation must be a MocShockCellObservation')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('area_tolerance_m2', area_tolerance_m2),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    shock = _points(observation.shock_boundary_points_m, 'shock boundary')
    centerline = _points(
      observation.centerline_boundary_points_m,
      'centerline boundary',
    )
  except ValueError as error:
    return _failure(
      MocShockCellMeasurementStatus.INVALID_INPUT,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(observation.shock_boundary_points_m),
      centerline_boundary_point_count=len(observation.centerline_boundary_points_m),
      message=str(error),
    )
  shock_error = _validate_polyline(
    shock,
    'shock boundary',
    position_tolerance_m=position_tolerance_m,
    require_strict_x=True,
  )
  centerline_error = _validate_polyline(
    centerline,
    'centerline boundary',
    position_tolerance_m=position_tolerance_m,
    require_strict_x=False,
  )
  if shock_error or centerline_error:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message=shock_error or centerline_error or 'boundary geometry is invalid',
    )
  if hypot(
      shock[-1][0] - centerline[0][0],
      shock[-1][1] - centerline[0][1],
  ) > position_tolerance_m:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message='shock and centerline boundaries must share their endpoint',
    )
  if abs(centerline[-1][1]) > axis_tolerance_m:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      message='centerline boundary must terminate on y = 0',
    )
  for cell_index, cell in enumerate(observation.cells):
    try:
      vertices = _cell_vertices(cell)
    except (AttributeError, TypeError, ValueError) as error:
      return _failure(
        MocShockCellMeasurementStatus.INVALID_INPUT,
        cell_index=observation.cell_index,
        cell_count=len(observation.cells),
        shock_boundary_point_count=len(shock),
        centerline_boundary_point_count=len(centerline),
        message=f'cell {cell_index} could not be read: {error}',
      )
    if any(
        len(point) != 2
        or not all(isfinite(float(coordinate)) for coordinate in point)
        or float(point[1]) < -axis_tolerance_m
        for point in vertices
    ):
      return _failure(
        MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
        cell_index=observation.cell_index,
        cell_count=len(observation.cells),
        shock_boundary_point_count=len(shock),
        centerline_boundary_point_count=len(centerline),
        message=f'cell {cell_index} leaves the nonnegative-y measurement half-plane',
      )
  topology = validate_moc_mesh(
    observation.cells,
    vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocShockCellMeasurementStatus.TOPOLOGY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=f'MOC cell mesh topology is not one bounded connected zone: {topology.message}',
    )
  try:
    edge_counts, vertex_points = _edge_counts(
      observation.cells,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (AttributeError, TypeError, ValueError) as error:
    return _failure(
      MocShockCellMeasurementStatus.INVALID_INPUT,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=f'cell mesh could not be measured: {error}',
    )
  if not _polyline_has_boundary_edges(
      shock,
      edge_counts,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
  ):
    message = 'shock boundary samples are not explicit perimeter edges in the mesh'
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=message,
    )
  if not _polyline_has_boundary_edges(
      centerline,
      edge_counts,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
  ):
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message='centerline boundary samples are not explicit perimeter edges in the mesh',
    )
  perimeter = _perimeter_points(edge_counts, vertex_points)
  if perimeter is None:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message='mesh perimeter could not be reconstructed as one cycle',
    )
  mesh_area = fsum(
    abs(_polygon_area(_cell_vertices(cell)))
    for cell in observation.cells
  )
  perimeter_area = abs(_polygon_area(perimeter))
  area_residual = mesh_area - perimeter_area
  scaled_area_tolerance = max(
    area_tolerance_m2,
    area_tolerance_m2 * max(1.0, perimeter_area),
  )
  if abs(area_residual) > scaled_area_tolerance:
    return _failure(
      MocShockCellMeasurementStatus.GEOMETRY_FAILURE,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      topology=topology,
      message=(
        'cell-area and perimeter-area measurements disagree beyond tolerance: '
        f'{area_residual}'
      ),
    )
  pressure_count, minimum_ratio, maximum_ratio, pressure_loss_verified, pressure_error = _pressure_metrics(
    observation.upstream_total_pressure_Pa,
    observation.downstream_total_pressure_Pa,
    expected_count=len(shock),
    zero_strength_shock_start_allowed=observation.zero_strength_shock_start_allowed,
    zero_strength_shock_endpoints_allowed=observation.zero_strength_shock_endpoints_allowed,
  )
  if pressure_error is not None:
    return MocShockCellMeasurement(
      status=MocShockCellMeasurementStatus.PRESSURE_FAILURE,
      operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
      cell_index=observation.cell_index,
      cell_count=len(observation.cells),
      topology=topology,
      shock_boundary_point_count=len(shock),
      centerline_boundary_point_count=len(centerline),
      shock_start_m=shock[0],
      shock_end_m=shock[-1],
      centerline_end_m=centerline[-1],
      axial_extent_m=(
        min(point[0] for point in (*shock, *centerline, *perimeter)),
        max(point[0] for point in (*shock, *centerline, *perimeter)),
      ),
      axial_length_m=max(point[0] for point in (*shock, *centerline, *perimeter))
      - min(point[0] for point in (*shock, *centerline, *perimeter)),
      shock_boundary_length_m=fsum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(shock, shock[1:])
      ),
      centerline_boundary_length_m=fsum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(centerline, centerline[1:])
      ),
      maximum_radius_m=max(point[1] for point in (*shock, *centerline, *perimeter)),
      mesh_area_m2=mesh_area,
      perimeter_area_m2=perimeter_area,
      area_closure_residual_m2=area_residual,
      pressure_sample_count=pressure_count,
      minimum_total_pressure_ratio=minimum_ratio,
      maximum_total_pressure_ratio=maximum_ratio,
      pressure_loss_verified=pressure_loss_verified,
      claim_status='not_accepted',
      message=pressure_error,
    )
  all_points = (*shock, *centerline, *perimeter)
  axial_min = min(point[0] for point in all_points)
  axial_max = max(point[0] for point in all_points)
  return MocShockCellMeasurement(
    status=MocShockCellMeasurementStatus.CONVERGED,
    operator_id=MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID,
    cell_index=observation.cell_index,
    cell_count=len(observation.cells),
    topology=topology,
    shock_boundary_point_count=len(shock),
    centerline_boundary_point_count=len(centerline),
    shock_start_m=shock[0],
    shock_end_m=shock[-1],
    centerline_end_m=centerline[-1],
    axial_extent_m=(axial_min, axial_max),
    axial_length_m=axial_max - axial_min,
    shock_boundary_length_m=fsum(
      hypot(second[0] - first[0], second[1] - first[1])
      for first, second in zip(shock, shock[1:])
    ),
    centerline_boundary_length_m=fsum(
      hypot(second[0] - first[0], second[1] - first[1])
      for first, second in zip(centerline, centerline[1:])
    ),
    maximum_radius_m=max(point[1] for point in all_points),
    mesh_area_m2=mesh_area,
    perimeter_area_m2=perimeter_area,
    area_closure_residual_m2=area_residual,
    pressure_sample_count=pressure_count,
    minimum_total_pressure_ratio=minimum_ratio,
    maximum_total_pressure_ratio=maximum_ratio,
    pressure_loss_verified=pressure_loss_verified,
    claim_status='not_accepted',
    message=(
      'shock-cell geometry and explicit perimeter topology measured; '
      'external comparison and physical-closure acceptance remain separate gates'
    ),
  )
####


def _terminal_measurement_failure(
  status: MocTerminalClosureMeasurementStatus,
  *,
  terminal_field_status: str | None = None,
  mixed_regime_status: str | None = None,
  supersonic_topology: MocTopologyResult | None = None,
  mixed_regime_topology: MocTopologyResult | None = None,
  terminal_shock_sample_count: int = 0,
  terminal_shock_edge_count: int = 0,
  terminal_shock_downstream_sample_count: int = 0,
  perimeter_sample_count: int = 0,
  supersonic_node_count: int = 0,
  supersonic_cell_count: int = 0,
  mixed_regime_node_count: int = 0,
  mixed_regime_cell_count: int = 0,
  terminal_normal_shock_verified: bool = False,
  terminal_shock_geometry_verified: bool = False,
  terminal_pressure_loss_verified: bool = False,
  supersonic_patch_verified: bool = False,
  mixed_regime_request_verified: bool = False,
  mixed_regime_boundary_verified: bool = False,
  mixed_regime_model_verified: bool = False,
  downstream_condition_verified: bool = False,
  physical_closure_verified: bool = False,
  physical_termination_verified: bool = False,
  minimum_terminal_total_pressure_ratio: float | None = None,
  maximum_terminal_total_pressure_ratio: float | None = None,
  maximum_thermodynamic_residual: float | None = None,
  maximum_harmonic_residual: float | None = None,
  maximum_velocity_divergence_residual: float | None = None,
  mixed_regime_potential_model_verified: bool | None = None,
  maximum_mass_conservation_residual: float | None = None,
  maximum_boundary_normal_velocity_residual: float | None = None,
  potential_circulation_residual: float | None = None,
  message: str,
) -> MocTerminalClosureMeasurement:
  return MocTerminalClosureMeasurement(
    status=status,
    operator_id=MOC_TERMINAL_CLOSURE_OPERATOR_ID,
    terminal_field_status=terminal_field_status,
    mixed_regime_status=mixed_regime_status,
    supersonic_topology=(
      _empty_topology() if supersonic_topology is None else supersonic_topology
    ),
    mixed_regime_topology=(
      _empty_topology()
      if mixed_regime_topology is None
      else mixed_regime_topology
    ),
    terminal_shock_sample_count=terminal_shock_sample_count,
    terminal_shock_edge_count=terminal_shock_edge_count,
    terminal_shock_downstream_sample_count=terminal_shock_downstream_sample_count,
    perimeter_sample_count=perimeter_sample_count,
    supersonic_node_count=supersonic_node_count,
    supersonic_cell_count=supersonic_cell_count,
    mixed_regime_node_count=mixed_regime_node_count,
    mixed_regime_cell_count=mixed_regime_cell_count,
    terminal_normal_shock_verified=terminal_normal_shock_verified,
    terminal_shock_geometry_verified=terminal_shock_geometry_verified,
    terminal_pressure_loss_verified=terminal_pressure_loss_verified,
    supersonic_patch_verified=supersonic_patch_verified,
    mixed_regime_request_verified=mixed_regime_request_verified,
    mixed_regime_boundary_verified=mixed_regime_boundary_verified,
    mixed_regime_model_verified=mixed_regime_model_verified,
    downstream_condition_verified=downstream_condition_verified,
    physical_closure_verified=physical_closure_verified,
    physical_termination_verified=physical_termination_verified,
    chain_promotion_blocked=True,
    minimum_terminal_total_pressure_ratio=minimum_terminal_total_pressure_ratio,
    maximum_terminal_total_pressure_ratio=maximum_terminal_total_pressure_ratio,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    mixed_regime_potential_model_verified=mixed_regime_potential_model_verified,
    maximum_mass_conservation_residual=maximum_mass_conservation_residual,
    maximum_boundary_normal_velocity_residual=(
      maximum_boundary_normal_velocity_residual
    ),
    potential_circulation_residual=potential_circulation_residual,
    claim_status='not_accepted',
    message=message,
  )
####


def _state_total_pressure(state: CharacteristicState, static_pressure_Pa: float) -> float:
  factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  return static_pressure_Pa * factor ** (state.gamma / (state.gamma - 1.0))
####


def _scalar_total_pressure(
  mach: float,
  gamma: float,
  static_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  return static_pressure_Pa * factor ** (gamma / (gamma - 1.0))
####


def _relative_value_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(1.0, abs(actual), abs(expected))
####


def _mixed_field_thermodynamic_residual(
  nodes: Sequence[MocMixedRegimeFieldSample],
) -> float | None:
  if not nodes:
    return None
  residuals: list[float] = []
  for sample in nodes:
    try:
      total_pressure = _scalar_total_pressure(
        sample.mach,
        sample.gamma,
        sample.static_pressure_Pa,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      return None
    residuals.append(
      _relative_value_residual(total_pressure, sample.total_pressure_Pa)
    )
  return max(residuals)
####


def _mixed_field_node_lookup(
  nodes: Sequence[MocMixedRegimeFieldSample],
  *,
  vertex_tolerance_m: float,
) -> dict[tuple[int, int], MocMixedRegimeFieldSample]:
  return {
    _key(sample.point_m, vertex_tolerance_m): sample
    for sample in nodes
  }
####


def _mixed_field_velocity_divergence_residual(
  field: MocMixedRegimeFieldResult,
  *,
  vertex_tolerance_m: float,
) -> float | None:
  if not field.cells:
    return None
  lookup = _mixed_field_node_lookup(
    field.nodes,
    vertex_tolerance_m=vertex_tolerance_m,
  )
  residuals: list[float] = []
  for cell in field.cells:
    try:
      vertices = _cell_vertices(cell)
    except (AttributeError, TypeError, ValueError):
      return None
    if len(vertices) != 3:
      return None
    samples = tuple(
      lookup.get(_key(point, vertex_tolerance_m))
      for point in vertices
    )
    if any(sample is None for sample in samples):
      return None
    first, second, third = samples
    assert first is not None
    assert second is not None
    assert third is not None
    x1, y1 = first.point_m
    x2, y2 = second.point_m
    x3, y3 = third.point_m
    area_twice = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    if abs(area_twice) <= 1.0e-20:
      return None
    velocities = tuple(
      (
        sample.mach * cos(sample.flow_angle_rad),
        sample.mach * sin(sample.flow_angle_rad),
      )
      for sample in (first, second, third)
    )
    du_dx = (
      velocities[0][0] * (y2 - y3)
      + velocities[1][0] * (y3 - y1)
      + velocities[2][0] * (y1 - y2)
    ) / area_twice
    dv_dy = (
      velocities[0][1] * (x3 - x2)
      + velocities[1][1] * (x1 - x3)
      + velocities[2][1] * (x2 - x1)
    ) / area_twice
    residuals.append(abs(du_dx + dv_dy))
  return max(residuals)
####


def _mixed_field_harmonic_residual(
  field: MocMixedRegimeFieldResult,
  *,
  position_tolerance_m: float,
) -> float | None:
  """Recompute the residual of the declared reference discretization."""

  boundary = field.boundary
  perimeter = boundary.perimeter_points_m
  samples = boundary.subsonic_samples
  if len(perimeter) < 4 or len(samples) != len(perimeter):
    return None
  unique_points = tuple(perimeter[:-1])
  unique_samples = tuple(samples[:-1])
  sample_count = len(unique_points)
  if sample_count < 3:
    return None
  if field.interior_point_m is None:
    return None
  if field.radial_divisions == 1:
    if len(field.nodes) != sample_count + 1:
      return None
    center = field.nodes[-1]
    if hypot(
        center.point_m[0] - field.interior_point_m[0],
        center.point_m[1] - field.interior_point_m[1],
    ) > position_tolerance_m:
      return None
    means = (
      fsum(sample.mach for sample in unique_samples) / sample_count,
      fsum(sample.flow_angle_rad for sample in unique_samples) / sample_count,
      fsum(sample.static_pressure_Pa for sample in unique_samples) / sample_count,
      fsum(sample.total_pressure_Pa for sample in unique_samples) / sample_count,
    )
    return max(
      abs(actual - expected)
      for actual, expected in zip(
        (
          center.mach,
          center.flow_angle_rad,
          center.static_pressure_Pa,
          center.total_pressure_Pa,
        ),
        means,
        strict=True,
      )
    )
  radial_divisions = field.radial_divisions
  expected_node_count = 1 + radial_divisions * sample_count
  if len(field.nodes) != expected_node_count:
    return None
  for level in range(radial_divisions + 1):
    level_points = (
      (field.interior_point_m,)
      if level == 0
      else tuple(
        (
          field.interior_point_m[0]
          + level / radial_divisions * (point[0] - field.interior_point_m[0]),
          field.interior_point_m[1]
          + level / radial_divisions * (point[1] - field.interior_point_m[1]),
        )
        for point in unique_points
      )
    )
    level_nodes = (
      (field.nodes[0],)
      if level == 0
      else tuple(
        field.nodes[1 + (level - 1) * sample_count + index]
        for index in range(sample_count)
      )
    )
    if any(
        hypot(node.point_m[0] - point[0], node.point_m[1] - point[1])
        > position_tolerance_m
        for node, point in zip(level_nodes, level_points, strict=True)
    ):
      return None
  residuals: list[float] = []
  components = (
    lambda sample: sample.mach,
    lambda sample: sample.flow_angle_rad,
    lambda sample: log(sample.total_pressure_Pa),
    lambda sample: sample.gamma,
  )
  for component in components:
    values = tuple(component(sample) for sample in field.nodes)
    residuals.append(
      abs(sample_count * values[0] - sum(
        values[1 + index] for index in range(sample_count)
      ))
    )
    for level in range(1, radial_divisions):
      for index in range(sample_count):
        row = 1 + (level - 1) * sample_count + index
        inner = 0.0 if level == 1 else values[
          1 + (level - 2) * sample_count + index
        ]
        outer = (
          values[1 + (radial_divisions - 1) * sample_count + index]
          if level + 1 == radial_divisions
          else values[1 + level * sample_count + index]
        )
        left = values[1 + (level - 1) * sample_count + (index - 1) % sample_count]
        right = values[1 + (level - 1) * sample_count + (index + 1) % sample_count]
        center = values[0] if level == 1 else inner
        residuals.append(abs(4.0 * values[row] - center - outer - left - right))
    if radial_divisions == 1:
      break
  return max(residuals, default=None)
####


def _potential_measurement_failure(
  status: MocMixedRegimePotentialMeasurementStatus,
  *,
  field: MocMixedRegimeFieldResult | None = None,
  topology: MocTopologyResult | None = None,
  boundary_verified: bool = False,
  potential_layout_verified: bool = False,
  maximum_thermodynamic_residual: float | None = None,
  maximum_mass_conservation_residual: float | None = None,
  maximum_boundary_velocity_residual: float | None = None,
  maximum_boundary_normal_velocity_residual: float | None = None,
  potential_circulation_residual: float | None = None,
  maximum_mach: float | None = None,
  message: str,
) -> MocMixedRegimePotentialMeasurement:
  return MocMixedRegimePotentialMeasurement(
    status=status,
    operator_id=MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID,
    model=None if field is None else field.model,
    radial_divisions=None if field is None else field.radial_divisions,
    node_count=0 if field is None else len(field.nodes),
    cell_count=0 if field is None else len(field.cells),
    topology=_empty_topology() if topology is None else topology,
    boundary_verified=boundary_verified,
    potential_layout_verified=potential_layout_verified,
    reference_model_verified=False,
    downstream_condition_verified=bool(
      field is not None
      and field.downstream_condition is not None
      and field.downstream_condition.converged
      and field.downstream_condition.boundary == field.boundary
    ),
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_mass_conservation_residual=maximum_mass_conservation_residual,
    maximum_boundary_velocity_residual=maximum_boundary_velocity_residual,
    maximum_boundary_normal_velocity_residual=(
      maximum_boundary_normal_velocity_residual
    ),
    potential_circulation_residual=potential_circulation_residual,
    maximum_mach=maximum_mach,
    nonlinear_iteration_count=(
      0 if field is None else field.nonlinear_iteration_count
    ),
    message=message,
  )


def _measurement_potential_primitive(
  q_x: float,
  q_y: float,
  gamma: float,
) -> tuple[float, float, float, float, float, float, float]:
  """Recompute the normalized compressible potential primitive independently."""

  speed_squared = q_x * q_x + q_y * q_y
  sonic_factor = 0.5 * (gamma - 1.0)
  enthalpy_factor = 1.0 - sonic_factor * speed_squared
  if enthalpy_factor <= 0.0:
    raise ValueError('potential measurement reached a nonphysical enthalpy factor')
  mach = sqrt(speed_squared / enthalpy_factor)
  density = enthalpy_factor ** (1.0 / (gamma - 1.0))
  jacobian_scale = density / enthalpy_factor
  return (
    mach,
    density * q_x,
    density * q_y,
    density - jacobian_scale * q_x * q_x,
    -jacobian_scale * q_x * q_y,
    -jacobian_scale * q_y * q_x,
    density - jacobian_scale * q_y * q_y,
  )


def _measurement_polygon_signed_area(points: Sequence[Point]) -> float:
  return 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]), strict=True)
  )


def _measure_boundary_normal_velocity_residual(
  unique_points: Sequence[Point],
  boundary_edge_velocities: dict[tuple[int, int], tuple[float, float]],
  *,
  outer_start: int,
  condition_edge_indices: Sequence[int],
  position_tolerance_m: float,
) -> float | None:
  """Independently measure normal velocity on selected outer edges."""

  if not condition_edge_indices:
    return None
  area = _measurement_polygon_signed_area(unique_points)
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    raise ValueError(
      'potential measurement perimeter has zero signed area for normal-flow measurement'
    )
  perimeter_count = len(unique_points)
  orientation = 1.0 if area > 0.0 else -1.0
  residuals: list[float] = []
  for edge_index in condition_edge_indices:
    if (
      isinstance(edge_index, bool)
      or not isinstance(edge_index, int)
      or edge_index < 0
      or edge_index >= perimeter_count
    ):
      raise ValueError(
        'potential measurement received an invalid normal-flow edge index'
      )
    next_index = (edge_index + 1) % perimeter_count
    displacement = (
      unique_points[next_index][0] - unique_points[edge_index][0],
      unique_points[next_index][1] - unique_points[edge_index][1],
    )
    segment_length = hypot(*displacement)
    if segment_length <= position_tolerance_m:
      raise ValueError(
        'potential measurement found a zero-length outer edge for normal-flow measurement'
      )
    first_node = outer_start + edge_index
    second_node = outer_start + next_index
    edge = (
      (first_node, second_node)
      if first_node <= second_node
      else (second_node, first_node)
    )
    velocity = boundary_edge_velocities.get(edge)
    if velocity is None:
      raise ValueError(
        'potential measurement could not find the adjacent triangle for '
        f'outer edge {edge_index}'
      )
    outward_normal = (
      orientation * displacement[1] / segment_length,
      -orientation * displacement[0] / segment_length,
    )
    residuals.append(abs(
      velocity[0] * outward_normal[0]
      + velocity[1] * outward_normal[1]
    ))
  return max(residuals, default=None)


def measure_mixed_regime_compressible_potential_field(
  field: MocMixedRegimeFieldResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  velocity_tolerance: float = 1.0e-8,
  subsonic_margin: float = 1.0e-6,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocMixedRegimePotentialMeasurement:
  """Independently measure a scalar compressible potential reference field.

  The operator treats the field as data.  It reconstructs the scalar seam,
  radial node layout, triangle potential gradients, compressible mass flux,
  boundary-potential residual, circulation, and strict-subsonic gate without
  reading the field's convenience acceptance properties.  This validates the
  explicit finite-domain reference only; it never turns it into a canonical
  free-boundary or supersonic-chain result.
  """

  if not isinstance(field, MocMixedRegimeFieldResult):
    raise TypeError('field must be a MocMixedRegimeFieldResult')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('potential_tolerance', potential_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('velocity_tolerance', velocity_tolerance),
    ('subsonic_margin', subsonic_margin),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if subsonic_margin >= 1.0:
    raise ValueError('subsonic_margin must be less than one')
  if field.model != 'compressible-isentropic-potential-reference':
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.INVALID_INPUT,
      field=field,
      message=(
        'potential measurement requires the explicitly named compressible '
        f'potential model, received {field.model!r}'
      ),
    )
  if not field.converged:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.FIELD_FAILURE,
      field=field,
      message=f'potential field is not converged: {field.message}',
    )

  boundary = field.boundary
  boundary_verified = False
  try:
    if boundary.terminal is not None:
      independent_boundary = validate_mixed_regime_boundary(
        boundary.terminal,
        boundary.supersonic_patch,
        supersonic_patch_converged=boundary.supersonic_patch_verified,
        subsonic_samples=boundary.subsonic_samples,
        perimeter_points_m=boundary.perimeter_points_m,
        position_tolerance_m=position_tolerance_m,
        pressure_tolerance=thermodynamic_tolerance,
      )
      boundary_verified = independent_boundary.converged
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    boundary_verified = False
  if not boundary_verified:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.BOUNDARY_FAILURE,
      field=field,
      boundary_verified=False,
      message='potential measurement could not independently verify the scalar seam',
    )

  perimeter = boundary.perimeter_points_m
  samples = boundary.subsonic_samples
  unique_points = tuple(perimeter[:-1])
  unique_samples = tuple(samples[:-1])
  if len(unique_points) < 3 or len(unique_points) != len(unique_samples):
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.BOUNDARY_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      message='potential measurement requires a closed perimeter with unique samples',
    )
  perimeter_count = len(unique_points)
  radial_divisions = field.radial_divisions
  expected_node_count = 1 + radial_divisions * perimeter_count
  unknown_count = 1 + (radial_divisions - 1) * perimeter_count
  outer_start = unknown_count
  if len(field.nodes) != expected_node_count:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.GEOMETRY_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      message=(
        'potential measurement node count does not match the declared radial '
        f'mesh: expected={expected_node_count}, actual={len(field.nodes)}'
      ),
    )
  if field.interior_point_m is None:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.GEOMETRY_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      message='potential measurement requires the radial mesh interior point',
    )
  expected_points = [field.interior_point_m]
  for level in range(1, radial_divisions + 1):
    scale = level / radial_divisions
    expected_points.extend(
      (
        field.interior_point_m[0] + scale * (point[0] - field.interior_point_m[0]),
        field.interior_point_m[1] + scale * (point[1] - field.interior_point_m[1]),
      )
      for point in unique_points
    )
  potential = tuple(float(value) for value in field.velocity_potential)
  layout_verified = len(potential) == expected_node_count and all(
    hypot(
      field.nodes[index].point_m[0] - point[0],
      field.nodes[index].point_m[1] - point[1],
    ) <= position_tolerance_m
    for index, point in enumerate(expected_points)
  )
  if not layout_verified:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.GEOMETRY_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      potential_layout_verified=False,
      message='potential measurement radial node/potential layout is inconsistent',
    )

  gamma_reference = unique_samples[0].gamma
  total_pressure_reference = unique_samples[0].total_pressure_Pa
  maximum_total_pressure_residual = max(
    _relative_value_residual(sample.total_pressure_Pa, total_pressure_reference)
    for sample in unique_samples
  )
  maximum_gamma_residual = max(
    _relative_value_residual(sample.gamma, gamma_reference)
    for sample in unique_samples
  )
  if (
    maximum_total_pressure_residual > thermodynamic_tolerance
    or maximum_gamma_residual > thermodynamic_tolerance
  ):
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      potential_layout_verified=layout_verified,
      maximum_thermodynamic_residual=max(
        maximum_total_pressure_residual,
        maximum_gamma_residual,
      ),
      message='potential measurement found nonuniform isentropic boundary data',
    )

  boundary_velocities: list[tuple[float, float]] = []
  try:
    sonic_factor = 0.5 * (gamma_reference - 1.0)
    for sample in unique_samples:
      speed = sample.mach / sqrt(
        1.0 + sonic_factor * sample.mach * sample.mach
      )
      boundary_velocities.append(
        (
          speed * cos(sample.flow_angle_rad),
          speed * sin(sample.flow_angle_rad),
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE,
      field=field,
      boundary_verified=boundary_verified,
      potential_layout_verified=layout_verified,
      message=f'potential measurement boundary velocity conversion failed: {error}',
    )

  circulation = 0.0
  for index, point in enumerate(unique_points):
    next_index = (index + 1) % perimeter_count
    displacement = (
      unique_points[next_index][0] - point[0],
      unique_points[next_index][1] - point[1],
    )
    circulation += 0.5 * (
      (boundary_velocities[index][0] + boundary_velocities[next_index][0]) * displacement[0]
      + (boundary_velocities[index][1] + boundary_velocities[next_index][1]) * displacement[1]
    )
  circulation_residual = abs(circulation)
  node_lookup = {
    _key(sample.point_m, mesh_vertex_tolerance_m): index
    for index, sample in enumerate(field.nodes)
  }
  mass_residuals = [0.0 for _ in range(unknown_count)]
  boundary_edge_velocities: dict[tuple[int, int], tuple[float, float]] = {}
  maximum_mach = 0.0
  try:
    for cell in field.cells:
      vertices = _cell_vertices(cell)
      if len(vertices) != 3:
        raise ValueError('potential measurement requires triangular cells')
      indices = tuple(
        node_lookup.get(_key(point, mesh_vertex_tolerance_m))
        for point in vertices
      )
      if any(index is None for index in indices):
        raise ValueError('potential measurement cell vertex is absent from the field nodes')
      resolved_indices = tuple(index for index in indices if index is not None)
      if len(resolved_indices) != 3:
        raise ValueError('potential measurement cell node lookup is incomplete')
      first, second, third = vertices
      area_twice = (
        (second[0] - first[0]) * (third[1] - first[1])
        - (second[1] - first[1]) * (third[0] - first[0])
      )
      if abs(area_twice) <= 1.0e-20:
        raise ValueError('potential measurement encountered a zero-area cell')
      gradients = (
        ((second[1] - third[1]) / area_twice, (third[0] - second[0]) / area_twice),
        ((third[1] - first[1]) / area_twice, (first[0] - third[0]) / area_twice),
        ((first[1] - second[1]) / area_twice, (second[0] - first[0]) / area_twice),
      )
      q_x = sum(
        potential[index] * gradients[local][0]
        for local, index in enumerate(resolved_indices)
      )
      q_y = sum(
        potential[index] * gradients[local][1]
        for local, index in enumerate(resolved_indices)
      )
      primitive = _measurement_potential_primitive(
        q_x,
        q_y,
        gamma_reference,
      )
      mach, flux_x, flux_y = primitive[:3]
      if mach >= 1.0 - subsonic_margin:
        raise ValueError(f'potential measurement found a sonic cell state: mach={mach}')
      maximum_mach = max(maximum_mach, mach)
      outer_nodes = tuple(sorted(
        index for index in resolved_indices if index >= outer_start
      ))
      if len(outer_nodes) == 2:
        outer_edge = (outer_nodes[0], outer_nodes[1])
        if outer_edge in boundary_edge_velocities:
          raise ValueError(
            'potential measurement found multiple adjacent triangles for '
            f'outer edge {outer_edge}'
          )
        boundary_edge_velocities[outer_edge] = (q_x, q_y)
      area = abs(area_twice) * 0.5
      for local, row_index in enumerate(resolved_indices):
        if row_index < unknown_count:
          mass_residuals[row_index] += area * (
            gradients[local][0] * flux_x
            + gradients[local][1] * flux_y
          )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE,
      field=field,
      topology=validate_moc_mesh(
        field.cells,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      ),
      boundary_verified=boundary_verified,
      potential_layout_verified=layout_verified,
      potential_circulation_residual=circulation_residual,
      maximum_mach=maximum_mach,
      message=f'potential measurement residual reconstruction failed: {error}',
    )

  boundary_velocity_residual = 0.0
  for index in range(perimeter_count):
    next_index = (index + 1) % perimeter_count
    displacement = (
      unique_points[next_index][0] - unique_points[index][0],
      unique_points[next_index][1] - unique_points[index][1],
    )
    segment_length = hypot(*displacement)
    if segment_length <= position_tolerance_m:
      return _potential_measurement_failure(
        MocMixedRegimePotentialMeasurementStatus.GEOMETRY_FAILURE,
        field=field,
        boundary_verified=boundary_verified,
        potential_layout_verified=layout_verified,
        potential_circulation_residual=circulation_residual,
        maximum_mach=maximum_mach,
        message='potential measurement found a zero-length perimeter segment',
      )
    tangent = (
      displacement[0] / segment_length,
      displacement[1] / segment_length,
    )
    computed = (
      potential[outer_start + next_index]
      - potential[outer_start + index]
    ) / segment_length
    prescribed = 0.5 * (
      (boundary_velocities[index][0] + boundary_velocities[next_index][0]) * tangent[0]
      + (boundary_velocities[index][1] + boundary_velocities[next_index][1]) * tangent[1]
    )
    boundary_velocity_residual = max(
      boundary_velocity_residual,
      abs(computed - prescribed),
    )

  boundary_normal_velocity_residual: float | None = None
  tangency_condition_required = bool(
    field.downstream_condition is not None
    and field.downstream_condition.tangency_condition_applicable
  )
  if tangency_condition_required:
    try:
      assert field.downstream_condition is not None
      boundary_normal_velocity_residual = (
        _measure_boundary_normal_velocity_residual(
          unique_points,
          boundary_edge_velocities,
          outer_start=outer_start,
          condition_edge_indices=field.downstream_condition.condition_edge_indices,
          position_tolerance_m=position_tolerance_m,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _potential_measurement_failure(
        MocMixedRegimePotentialMeasurementStatus.GEOMETRY_FAILURE,
        field=field,
        topology=validate_moc_mesh(
          field.cells,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        ),
        boundary_verified=boundary_verified,
        potential_layout_verified=layout_verified,
        potential_circulation_residual=circulation_residual,
        maximum_mach=maximum_mach,
        message=f'potential measurement normal-flow reconstruction failed: {error}',
      )

  topology = validate_moc_mesh(
    field.cells,
    vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  thermodynamic_residual = _mixed_field_thermodynamic_residual(field.nodes)
  if thermodynamic_residual is not None:
    thermodynamic_residual = max(
      thermodynamic_residual,
      maximum_total_pressure_residual,
      maximum_gamma_residual,
    )
  mass_residual = max(abs(value) for value in mass_residuals)
  model_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and not topology.nonmanifold_edge_count
    and thermodynamic_residual is not None
    and thermodynamic_residual <= thermodynamic_tolerance
    and mass_residual <= residual_tolerance
    and boundary_velocity_residual <= velocity_tolerance
    and (
      not tangency_condition_required
      or (
        boundary_normal_velocity_residual is not None
        and boundary_normal_velocity_residual <= velocity_tolerance
      )
    )
    and circulation_residual <= potential_tolerance * max(
      1.0,
      max(
        hypot(
          unique_points[(index + 1) % perimeter_count][0] - point[0],
          unique_points[(index + 1) % perimeter_count][1] - point[1],
        )
        for index, point in enumerate(unique_points)
      )
      * max(1.0, max(hypot(*velocity) for velocity in boundary_velocities)),
    )
    and maximum_mach < 1.0 - subsonic_margin
  )
  if not model_verified:
    return _potential_measurement_failure(
      MocMixedRegimePotentialMeasurementStatus.RESIDUAL_FAILURE,
      field=field,
      topology=topology,
      boundary_verified=boundary_verified,
      potential_layout_verified=layout_verified,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_mass_conservation_residual=mass_residual,
      maximum_boundary_velocity_residual=boundary_velocity_residual,
      maximum_boundary_normal_velocity_residual=(
        boundary_normal_velocity_residual
      ),
      potential_circulation_residual=circulation_residual,
      maximum_mach=maximum_mach,
      message=(
        'independent compressible potential residual gate failed: '
        f'thermodynamic={thermodynamic_residual}, mass={mass_residual}, '
        f'boundary_velocity={boundary_velocity_residual}, '
        f'boundary_normal_velocity={boundary_normal_velocity_residual}, '
        f'circulation={circulation_residual}, maximum_mach={maximum_mach}'
      ),
    )
  return MocMixedRegimePotentialMeasurement(
    status=MocMixedRegimePotentialMeasurementStatus.CONVERGED,
    operator_id=MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID,
    model=field.model,
    radial_divisions=radial_divisions,
    node_count=len(field.nodes),
    cell_count=len(field.cells),
    topology=topology,
    boundary_verified=boundary_verified,
    potential_layout_verified=layout_verified,
    reference_model_verified=True,
    downstream_condition_verified=bool(
      field.downstream_condition is not None
      and field.downstream_condition.converged
      and field.downstream_condition.boundary == boundary
    ),
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_mass_conservation_residual=mass_residual,
    maximum_boundary_velocity_residual=boundary_velocity_residual,
    maximum_boundary_normal_velocity_residual=(
      boundary_normal_velocity_residual
    ),
    potential_circulation_residual=circulation_residual,
    maximum_mach=maximum_mach,
    nonlinear_iteration_count=field.nonlinear_iteration_count,
    message=(
      'independent compressible potential measurement passed the explicit '
      'perimeter, radial layout, nonlinear mass, circulation, applicable '
      'no-penetration, and subsonic gates; it remains a non-canonical scalar '
      'reference'
    ),
  )
####


def _planar_free_boundary_measurement_failure(
  status: MocMixedRegimePlanarFreeBoundaryMeasurementStatus,
  *,
  result: MocMixedRegimePlanarFreeBoundaryResult | None = None,
  topology: MocTopologyResult | None = None,
  potential_measurement: MocMixedRegimePotentialMeasurement | None = None,
  request_verified: bool = False,
  control_section_verified: bool = False,
  perimeter_spec_verified: bool = False,
  boundary_verified: bool = False,
  downstream_condition_verified: bool = False,
  field_measurement_verified: bool = False,
  shape_geometry_verified: bool = False,
  free_boundary_residual_verified: bool = False,
  physical_closure_verified: bool = False,
  maximum_boundary_normal_velocity_residual: float | None = None,
  independent_boundary_normal_velocity_residual: float | None = None,
  maximum_tangent_residual_rad: float | None = None,
  maximum_pressure_residual_Pa: float | None = None,
  message: str,
) -> MocMixedRegimePlanarFreeBoundaryMeasurement:
  field = None if result is None else result.field
  return MocMixedRegimePlanarFreeBoundaryMeasurement(
    status=status,
    operator_id=MOC_MIXED_REGIME_PLANAR_FREE_BOUNDARY_OPERATOR_ID,
    model=None if result is None else result.model,
    solver_status=None if result is None else result.status.value,
    potential_measurement_status=(
      None if potential_measurement is None
      else potential_measurement.status.value
    ),
    node_count=0 if field is None else len(field.nodes),
    cell_count=0 if field is None else len(field.cells),
    topology=_empty_topology() if topology is None else topology,
    request_verified=request_verified,
    control_section_verified=control_section_verified,
    perimeter_spec_verified=perimeter_spec_verified,
    boundary_verified=boundary_verified,
    downstream_condition_verified=downstream_condition_verified,
    field_measurement_verified=field_measurement_verified,
    shape_geometry_verified=shape_geometry_verified,
    free_boundary_residual_verified=free_boundary_residual_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    maximum_boundary_normal_velocity_residual=(
      maximum_boundary_normal_velocity_residual
    ),
    independent_boundary_normal_velocity_residual=(
      independent_boundary_normal_velocity_residual
    ),
    maximum_tangent_residual_rad=maximum_tangent_residual_rad,
    maximum_pressure_residual_Pa=maximum_pressure_residual_Pa,
    message=message,
  )


def measure_mixed_regime_planar_free_boundary_reference(
  result: MocMixedRegimePlanarFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  velocity_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocMixedRegimePlanarFreeBoundaryMeasurement:
  """Independently measure the parameterized planar free-boundary reference.

  The result is treated as data.  This operator reconstructs the expected
  terminal/centerline/envelope perimeter from the declared shape samples,
  revalidates the scalar seams and selected ambient condition, and sends the
  retained field through the independent compressible-potential measurement.
  A passing record is local research evidence only; it does not establish a
  canonical reflected-MOC free boundary or permit chain promotion.
  """

  if not isinstance(result, MocMixedRegimePlanarFreeBoundaryResult):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message=(
        'result must be a MocMixedRegimePlanarFreeBoundaryResult'
      ),
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('potential_tolerance', potential_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('velocity_tolerance', velocity_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  expected_model = (
    'parameterized-2d-compressible-potential-free-boundary-reference'
  )
  if result.model != expected_model:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.INVALID_INPUT,
      result=result,
      message=(
        'planar free-boundary measurement requires the explicitly named '
        f'research model, received {result.model!r}'
      ),
    )
  if not result.converged:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      result=result,
      message=(
        'planar free-boundary measurement requires a converged returned '
        f'field and handoff: {result.message}'
      ),
    )

  request = result.request
  control_section = result.control_section
  field = result.field
  boundary = result.boundary
  specification = result.perimeter_spec
  condition = result.downstream_condition
  if not isinstance(control_section, MocMixedRegimeControlSection):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONTROL_SECTION_FAILURE,
      result=result,
      message='planar free-boundary result did not retain its control section',
    )
  try:
    independent_control_section = validate_mixed_regime_control_section(
      request,
      control_section,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
      normal_flux_tolerance=normal_flux_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONTROL_SECTION_FAILURE,
      result=result,
      message=f'control section could not be independently remeasured: {error}',
    )
  control_section_verified = bool(
    independent_control_section.converged
    and independent_control_section.request == request
    and independent_control_section.section == control_section
    and result.control_section_validation == independent_control_section
  )
  if not control_section_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONTROL_SECTION_FAILURE,
      result=result,
      control_section_verified=False,
      message=(
        'independent control-section validation failed or did not match the '
        f'reported validation: {independent_control_section.message}'
      ),
    )

  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      control_section_verified=control_section_verified,
      message='planar free-boundary result did not retain its scalar boundary',
    )
  if not isinstance(specification, MocMixedRegimeDownstreamPerimeterSpec):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      control_section_verified=control_section_verified,
      message=(
        'planar free-boundary result did not retain its perimeter specification'
      ),
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      result=result,
      control_section_verified=control_section_verified,
      message='planar free-boundary result did not retain its potential field',
    )
  if not isinstance(condition, MocMixedRegimeDownstreamConditionResult):
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      result=result,
      control_section_verified=control_section_verified,
      message=(
        'planar free-boundary result did not retain its downstream condition'
      ),
    )

  request_verified = bool(
    field.boundary == boundary
    and field.control_section == control_section
    and boundary.terminal == request.terminal
    and boundary.supersonic_patch == request.supersonic_patch
    and boundary.supersonic_patch_sample_count == len(request.supersonic_patch)
  )
  if not request_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=False,
      control_section_verified=control_section_verified,
      message=(
        'planar free-boundary field does not retain the exact requested '
        'terminal, supersonic patch, and control-section seams'
      ),
    )

  try:
    independent_boundary = validate_mixed_regime_boundary(
      request.terminal,
      request.supersonic_patch,
      supersonic_patch_converged=True,
      subsonic_samples=boundary.subsonic_samples,
      perimeter_points_m=boundary.perimeter_points_m,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      message=f'scalar perimeter could not be independently remeasured: {error}',
    )
  boundary_verified = independent_boundary.converged
  if not boundary_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      boundary_verified=False,
      message=(
        'independent scalar perimeter validation failed: '
        f'{independent_boundary.message}'
      ),
    )

  def same_points(
    first: Sequence[tuple[float, float]],
    second: Sequence[tuple[float, float]],
  ) -> bool:
    return bool(
      len(first) == len(second)
      and all(
        hypot(left[0] - right[0], left[1] - right[1])
        <= position_tolerance_m
        for left, right in zip(first, second, strict=True)
      )
    )

  shape_geometry_verified = False
  expected_points: tuple[tuple[float, float], ...] = ()
  shape = tuple(result.shape_heights_m)
  try:
    sample_count = result.free_boundary_sample_count
    centerline_count = result.centerline_sample_count
    if len(shape) != sample_count:
      raise ValueError(
        'shape_heights_m does not match free_boundary_sample_count'
      )
    segment_length = result.downstream_length_m / sample_count
    free_ascending = tuple(
      (
        request.terminal_point_m[0] + segment_length * index,
        request.terminal_point_m[1] + shape[index - 1],
      )
      for index in range(1, sample_count + 1)
    )
    centerline = tuple(
      (
        request.terminal_point_m[0]
        + result.downstream_length_m * index / centerline_count,
        request.terminal_point_m[1],
      )
      for index in range(1, centerline_count + 1)
    )
    expected_points = (
      request.terminal_point_m,
      *centerline,
      *tuple(reversed(free_ascending)),
      request.terminal_point_m,
    )
    slopes = tuple(
      (second - first) / segment_length
      for first, second in zip(shape[:-1], shape[1:], strict=True)
    )
    shape_geometry_verified = bool(
      all(isfinite(value) and value > position_tolerance_m for value in shape)
      and abs(shape[-1] - result.outlet_height_m) <= position_tolerance_m
      and all(
        second >= first - position_tolerance_m
        for first, second in zip(shape[:-1], shape[1:], strict=True)
      )
      and all(
        second <= first + position_tolerance_m
        for first, second in zip(slopes[:-1], slopes[1:], strict=True)
      )
      and same_points(specification.perimeter_points_m, expected_points)
      and same_points(boundary.perimeter_points_m, expected_points)
    )
  except (ArithmeticError, FloatingPointError, IndexError, TypeError, ValueError):
    shape_geometry_verified = False
  if not shape_geometry_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      boundary_verified=boundary_verified,
      message=(
        'reported free-boundary shape heights do not reconstruct the explicit '
        'terminal/centerline/envelope perimeter'
      ),
    )

  free_start_index = 1 + result.centerline_sample_count
  expected_condition_edges = tuple(
    range(
      free_start_index,
      free_start_index + result.free_boundary_sample_count - 1,
    )
  )
  expected_condition_samples = tuple(
    range(
      free_start_index,
      free_start_index + result.free_boundary_sample_count,
    )
  )
  pressure_scale = max(1.0, abs(result.ambient_pressure_Pa))
  perimeter_spec_verified = bool(
    specification.model == result.model
    and specification.condition_kind is (
      MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY
    )
    and same_points(specification.perimeter_points_m, boundary.perimeter_points_m)
    and specification.ambient_pressure_Pa is not None
    and abs(specification.ambient_pressure_Pa - result.ambient_pressure_Pa)
    <= pressure_tolerance * pressure_scale
    and specification.condition_edge_indices == expected_condition_edges
    and specification.condition_sample_indices == expected_condition_samples
  )
  if not perimeter_spec_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      boundary_verified=boundary_verified,
      shape_geometry_verified=shape_geometry_verified,
      message=(
        'reported perimeter specification does not match the reconstructed '
        'free-boundary geometry or selected condition edges'
      ),
    )

  try:
    independent_condition = validate_mixed_regime_downstream_condition(
      independent_boundary,
      specification.condition_kind,
      ambient_pressure_Pa=specification.ambient_pressure_Pa,
      condition_edge_indices=specification.condition_edge_indices,
      condition_sample_indices=specification.condition_sample_indices,
      position_tolerance_m=position_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      boundary_verified=boundary_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      shape_geometry_verified=shape_geometry_verified,
      message=f'downstream condition could not be independently remeasured: {error}',
    )
  downstream_condition_verified = bool(
    independent_condition.converged
    and condition.converged
    and condition.boundary == boundary
    and condition.condition_kind is specification.condition_kind
    and condition.condition_edge_indices == expected_condition_edges
    and condition.condition_sample_indices == expected_condition_samples
    and field.downstream_condition == condition
  )
  if not downstream_condition_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      boundary_verified=boundary_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      downstream_condition_verified=False,
      shape_geometry_verified=shape_geometry_verified,
      maximum_tangent_residual_rad=(
        independent_condition.maximum_tangent_residual_rad
      ),
      maximum_pressure_residual_Pa=(
        independent_condition.maximum_pressure_residual_Pa
      ),
      message=(
        'downstream condition did not pass the independent tangent/pressure '
        f'check: {independent_condition.message}'
      ),
    )

  try:
    potential_measurement = measure_mixed_regime_compressible_potential_field(
      field,
      position_tolerance_m=position_tolerance_m,
      thermodynamic_tolerance=thermodynamic_tolerance,
      potential_tolerance=potential_tolerance,
      residual_tolerance=residual_tolerance,
      velocity_tolerance=velocity_tolerance,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      result=result,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      boundary_verified=boundary_verified,
      downstream_condition_verified=downstream_condition_verified,
      shape_geometry_verified=shape_geometry_verified,
      maximum_tangent_residual_rad=(
        independent_condition.maximum_tangent_residual_rad
      ),
      maximum_pressure_residual_Pa=(
        independent_condition.maximum_pressure_residual_Pa
      ),
      message=f'independent potential measurement failed: {error}',
    )
  topology = potential_measurement.topology
  field_measurement_verified = bool(
    potential_measurement.converged
    and potential_measurement.reference_model_verified
    and potential_measurement.downstream_condition_verified
  )
  if not field_measurement_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      result=result,
      topology=topology,
      potential_measurement=potential_measurement,
      request_verified=request_verified,
      control_section_verified=control_section_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      boundary_verified=boundary_verified,
      downstream_condition_verified=downstream_condition_verified,
      shape_geometry_verified=shape_geometry_verified,
      maximum_tangent_residual_rad=(
        independent_condition.maximum_tangent_residual_rad
      ),
      maximum_pressure_residual_Pa=(
        independent_condition.maximum_pressure_residual_Pa
      ),
      independent_boundary_normal_velocity_residual=(
        potential_measurement.maximum_boundary_normal_velocity_residual
      ),
      message=(
        'independent compressible-potential field measurement failed its '
        f'local gates: {potential_measurement.message}'
      ),
    )

  independent_residual = (
    potential_measurement.maximum_boundary_normal_velocity_residual
  )
  reported_residual = result.maximum_boundary_normal_velocity_residual
  field_reported_residual = field.maximum_boundary_normal_velocity_residual
  stored_residuals = tuple(result.signed_free_boundary_residuals)
  stored_vector_maximum = (
    max((abs(value) for value in stored_residuals), default=None)
  )

  def residual_matches(actual: float | None, expected: float | None) -> bool:
    return bool(
      actual is not None
      and expected is not None
      and isfinite(float(actual))
      and isfinite(float(expected))
      and abs(actual - expected)
      <= residual_tolerance * max(1.0, abs(actual), abs(expected))
    )

  free_boundary_residual_verified = bool(
    len(stored_residuals) == result.free_boundary_sample_count - 1
    and independent_residual is not None
    and isfinite(float(independent_residual))
    and independent_residual <= velocity_tolerance
    and residual_matches(reported_residual, independent_residual)
    and residual_matches(field_reported_residual, independent_residual)
    and residual_matches(stored_vector_maximum, reported_residual)
  )
  physical_closure_verified = bool(
    result.converged
    and result.field is not None
    and result.field.physical_closure_verified
    and isinstance(result.closure, MocMixedRegimeClosureResult)
    and result.closure.converged
    and result.closure.request == request
    and result.closure.field == field
    and result.closure.downstream_condition == condition
    and result.closure.perimeter_spec == specification
    and request_verified
    and control_section_verified
    and perimeter_spec_verified
    and boundary_verified
    and downstream_condition_verified
    and field_measurement_verified
    and shape_geometry_verified
    and free_boundary_residual_verified
  )
  metrics = {
    'topology': topology,
    'potential_measurement': potential_measurement,
    'request_verified': request_verified,
    'control_section_verified': control_section_verified,
    'perimeter_spec_verified': perimeter_spec_verified,
    'boundary_verified': boundary_verified,
    'downstream_condition_verified': downstream_condition_verified,
    'field_measurement_verified': field_measurement_verified,
    'shape_geometry_verified': shape_geometry_verified,
    'free_boundary_residual_verified': free_boundary_residual_verified,
    'physical_closure_verified': physical_closure_verified,
    'maximum_boundary_normal_velocity_residual': reported_residual,
    'independent_boundary_normal_velocity_residual': independent_residual,
    'maximum_tangent_residual_rad': independent_condition.maximum_tangent_residual_rad,
    'maximum_pressure_residual_Pa': independent_condition.maximum_pressure_residual_Pa,
  }
  if not physical_closure_verified:
    return _planar_free_boundary_measurement_failure(
      MocMixedRegimePlanarFreeBoundaryMeasurementStatus.RESIDUAL_FAILURE,
      result=result,
      **metrics,
      message=(
        'independent planar free-boundary reference gates failed: '
        f'field={field_measurement_verified}, '
        f'geometry={shape_geometry_verified}, '
        f'normal_residual={free_boundary_residual_verified}'
      ),
    )
  return _planar_free_boundary_measurement_failure(
    MocMixedRegimePlanarFreeBoundaryMeasurementStatus.CONVERGED,
    result=result,
    **metrics,
    message=(
      'independent parameterized planar free-boundary measurement passed the '
      'exact seam, reconstructed geometry, tangent/pressure condition, '
      'potential-field, and normal-residual gates; canonical promotion remains '
      'blocked'
    ),
  )
####


def _planar_free_boundary_refinement_failure(
  status: MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocMixedRegimePlanarFreeBoundaryRefinementCase] = (),
  measurements: Sequence[MocMixedRegimePlanarFreeBoundaryMeasurement] = (),
  resolution_order_verified: bool = False,
  resolution_metadata_verified: bool = False,
  request_consistent: bool = False,
  control_section_consistent: bool = False,
  solver_configuration_consistent: bool = False,
  local_reference_closure_verified: bool = False,
  shape_convergence_verified: bool = False,
  centerline_speed_convergence_verified: bool = False,
  mesh_area_convergence_verified: bool = False,
  residuals_verified: bool = False,
  shape_delta_residuals_m: Sequence[float] = (),
  centerline_speed_delta_residuals: Sequence[float] = (),
  mesh_area_delta_residuals_m2: Sequence[float] = (),
  maximum_normal_velocity_residuals: Sequence[float | None] = (),
  refinement_convergence_verified: bool = False,
  physical_closure_verified: bool = False,
) -> MocMixedRegimePlanarFreeBoundaryRefinementMeasurement:
  valid_cases = tuple(
    case
    for case in cases
    if isinstance(case, MocMixedRegimePlanarFreeBoundaryRefinementCase)
  )
  valid_measurements = tuple(
    measurement
    for measurement in measurements
    if isinstance(measurement, MocMixedRegimePlanarFreeBoundaryMeasurement)
  )
  paired_count = min(len(valid_cases), len(valid_measurements))
  return MocMixedRegimePlanarFreeBoundaryRefinementMeasurement(
    status=status,
    cases=valid_cases[:paired_count],
    measurements=valid_measurements[:paired_count],
    resolution_order_verified=resolution_order_verified,
    resolution_metadata_verified=resolution_metadata_verified,
    request_consistent=request_consistent,
    control_section_consistent=control_section_consistent,
    solver_configuration_consistent=solver_configuration_consistent,
    local_reference_closure_verified=local_reference_closure_verified,
    shape_convergence_verified=shape_convergence_verified,
    centerline_speed_convergence_verified=centerline_speed_convergence_verified,
    mesh_area_convergence_verified=mesh_area_convergence_verified,
    residuals_verified=residuals_verified,
    shape_delta_residuals_m=tuple(shape_delta_residuals_m),
    centerline_speed_delta_residuals=tuple(centerline_speed_delta_residuals),
    mesh_area_delta_residuals_m2=tuple(mesh_area_delta_residuals_m2),
    maximum_normal_velocity_residuals=tuple(maximum_normal_velocity_residuals),
    refinement_convergence_verified=refinement_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status=(
      'not-accepted; parameterized-planar-free-boundary-refinement-only'
    ),
    message=message,
  )
####


def _planar_free_boundary_mesh_area(
  result: MocMixedRegimePlanarFreeBoundaryResult,
) -> float | None:
  field = result.field
  if field is None or not field.cells:
    return None
  try:
    area = fsum(
      abs(_polygon_area(_cell_vertices(cell)))
      for cell in field.cells
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  return area if isfinite(area) and area > 0.0 else None
####


def _planar_free_boundary_resampled_shape(
  result: MocMixedRegimePlanarFreeBoundaryResult,
  sample_count: int,
) -> tuple[float, ...] | None:
  shape = tuple(result.shape_heights_m)
  if len(shape) < 2 or sample_count < 2:
    return None
  if any(not isfinite(value) for value in shape):
    return None
  values: list[float] = []
  last_index = len(shape) - 1
  for index in range(sample_count):
    coordinate = index * last_index / (sample_count - 1)
    lower = min(last_index - 1, int(coordinate))
    fraction = coordinate - lower
    values.append(
      shape[lower] + fraction * (shape[lower + 1] - shape[lower])
    )
  return tuple(values)
####


def measure_mixed_regime_planar_free_boundary_refinement(
  cases: Sequence[MocMixedRegimePlanarFreeBoundaryRefinementCase],
  *,
  shape_tolerance_m: float = 5.0e-3,
  centerline_speed_tolerance: float = 1.0e-2,
  mesh_area_tolerance_m2: float = 1.0e-3,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  thermodynamic_tolerance: float = 1.0e-8,
  potential_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  velocity_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocMixedRegimePlanarFreeBoundaryRefinementMeasurement:
  """Compare independently measured planar reference results by resolution.

  The operator requires fresh reruns at strictly increasing free-boundary
  sample counts, remeasures each raw result, and compares the envelope shape,
  normalized centerline speed, and mesh area.  These are numerical-sensitivity
  gates for the bounded potential reference; they are not evidence that the
  canonical reflected-MOC mixed-regime boundary has been solved.
  """

  for name, value in (
    ('shape_tolerance_m', shape_tolerance_m),
    ('centerline_speed_tolerance', centerline_speed_tolerance),
    ('mesh_area_tolerance_m2', mesh_area_tolerance_m2),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('potential_tolerance', potential_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('velocity_tolerance', velocity_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    items = tuple(cases)
  except TypeError:
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  if len(items) < 2:
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'at least two planar free-boundary refinement cases are required',
    )
  if any(
    not isinstance(case, MocMixedRegimePlanarFreeBoundaryRefinementCase)
    for case in items
  ):
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain planar free-boundary refinement cases',
      cases=items,
    )
  resolutions = tuple(case.resolution for case in items)
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
      cases=items,
    )

  results = tuple(case.result for case in items)
  measurements = tuple(
    measure_mixed_regime_planar_free_boundary_reference(
      result,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
      normal_flux_tolerance=normal_flux_tolerance,
      tangent_tolerance_rad=tangent_tolerance_rad,
      thermodynamic_tolerance=thermodynamic_tolerance,
      potential_tolerance=potential_tolerance,
      residual_tolerance=residual_tolerance,
      velocity_tolerance=velocity_tolerance,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for result in results
  )
  perimeter_sample_counts = tuple(
    0 if result.boundary is None else len(result.boundary.perimeter_points_m)
    for result in results
  )
  maximum_normal_velocity_residuals = tuple(
    measurement.independent_boundary_normal_velocity_residual
    for measurement in measurements
  )
  case_measurements_verified = all(
    measurement.converged for measurement in measurements
  )
  resolution_metadata_verified = all(
    case.resolution == case.result.free_boundary_sample_count
    for case in items
  )
  local_reference_closure_verified = bool(
    case_measurements_verified
    and all(
      measurement.physical_closure_verified
      and measurement.chain_promotion_blocked
      and not measurement.production_claim_allowed
      and result.physical_closure_verified
      and not result.canonical_free_boundary_verified
      for result, measurement in zip(results, measurements, strict=True)
    )
  )

  def _consistent_float(values: Sequence[float]) -> bool:
    if not values:
      return False
    reference = float(values[0])
    return all(
      abs(float(value) - reference)
      <= 1.0e-12 * max(1.0, abs(float(value)), abs(reference))
      for value in values[1:]
    )

  request_consistent = all(
    result.request == results[0].request
    for result in results[1:]
  )
  control_section_consistent = all(
    result.control_section == results[0].control_section
    for result in results[1:]
  )
  solver_configuration_consistent = bool(
    len({result.model for result in results}) == 1
    and _consistent_float(tuple(result.ambient_pressure_Pa for result in results))
    and _consistent_float(tuple(result.downstream_length_m for result in results))
    and _consistent_float(tuple(result.outlet_height_m for result in results))
    and len({result.centerline_sample_count for result in results}) == 1
    and len({result.radial_divisions for result in results}) == 1
  )
  perimeter_resolution_verified = all(
    right > left
    for left, right in zip(perimeter_sample_counts, perimeter_sample_counts[1:])
  ) and all(count > 0 for count in perimeter_sample_counts)
  shape_samples = tuple(
    _planar_free_boundary_resampled_shape(result, 33)
    for result in results
  )
  shape_delta_residuals = tuple(
    max(abs(left - right) for left, right in zip(first, second, strict=True))
    for first, second in zip(shape_samples, shape_samples[1:])
    if first is not None and second is not None
  )
  centerline_speeds = tuple(
    result.centerline_speed_m_s_normalized for result in results
  )
  centerline_speed_delta_residuals = tuple(
    abs(float(current) - float(previous))
    for previous, current in zip(centerline_speeds, centerline_speeds[1:])
    if previous is not None and current is not None
  )
  mesh_areas = tuple(_planar_free_boundary_mesh_area(result) for result in results)
  mesh_area_delta_residuals = tuple(
    abs(float(current) - float(previous))
    for previous, current in zip(mesh_areas, mesh_areas[1:])
    if previous is not None and current is not None
  )
  shape_convergence_verified = bool(
    len(shape_delta_residuals) == len(items) - 1
    and all(residual <= float(shape_tolerance_m) for residual in shape_delta_residuals)
  )
  centerline_speed_convergence_verified = bool(
    len(centerline_speed_delta_residuals) == len(items) - 1
    and all(
      residual <= float(centerline_speed_tolerance)
      for residual in centerline_speed_delta_residuals
    )
  )
  mesh_area_convergence_verified = bool(
    len(mesh_area_delta_residuals) == len(items) - 1
    and all(
      residual <= float(mesh_area_tolerance_m2)
      for residual in mesh_area_delta_residuals
    )
  )
  residuals_verified = bool(
    len(maximum_normal_velocity_residuals) == len(items)
    and all(
      residual is not None
      and isfinite(float(residual))
      and float(residual) <= float(velocity_tolerance)
      for residual in maximum_normal_velocity_residuals
    )
  )
  refinement_convergence_verified = bool(
    case_measurements_verified
    and resolution_metadata_verified
    and request_consistent
    and control_section_consistent
    and solver_configuration_consistent
    and perimeter_resolution_verified
    and local_reference_closure_verified
    and shape_convergence_verified
    and centerline_speed_convergence_verified
    and mesh_area_convergence_verified
    and residuals_verified
  )
  common = {
    'cases': items,
    'measurements': measurements,
    'resolution_order_verified': True,
    'resolution_metadata_verified': resolution_metadata_verified,
    'request_consistent': request_consistent,
    'control_section_consistent': control_section_consistent,
    'solver_configuration_consistent': solver_configuration_consistent,
    'local_reference_closure_verified': local_reference_closure_verified,
    'shape_convergence_verified': shape_convergence_verified,
    'centerline_speed_convergence_verified': centerline_speed_convergence_verified,
    'mesh_area_convergence_verified': mesh_area_convergence_verified,
    'residuals_verified': residuals_verified,
    'shape_delta_residuals_m': shape_delta_residuals,
    'centerline_speed_delta_residuals': centerline_speed_delta_residuals,
    'mesh_area_delta_residuals_m2': mesh_area_delta_residuals,
    'maximum_normal_velocity_residuals': maximum_normal_velocity_residuals,
    'refinement_convergence_verified': refinement_convergence_verified,
    'physical_closure_verified': refinement_convergence_verified,
  }
  if not case_measurements_verified:
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.CASE_FAILURE,
      'one or more planar free-boundary cases failed independent measurement',
      **common,
    )
  if not (
    resolution_metadata_verified
    and request_consistent
    and control_section_consistent
    and solver_configuration_consistent
    and perimeter_resolution_verified
  ):
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'planar free-boundary reruns must retain one exact seam and fixed solver '
      'parameters while increasing the free-boundary resolution',
      **common,
    )
  if not refinement_convergence_verified:
    return _planar_free_boundary_refinement_failure(
      MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.SENSITIVITY_FAILURE,
      'planar free-boundary shape, centerline speed, mesh area, or residual '
      'sensitivity exceeded the declared tolerances',
      **common,
    )
  return MocMixedRegimePlanarFreeBoundaryRefinementMeasurement(
    status=MocMixedRegimePlanarFreeBoundaryRefinementMeasurementStatus.CONVERGED,
    cases=items,
    measurements=measurements,
    resolution_order_verified=True,
    resolution_metadata_verified=True,
    request_consistent=True,
    control_section_consistent=True,
    solver_configuration_consistent=True,
    local_reference_closure_verified=True,
    shape_convergence_verified=True,
    centerline_speed_convergence_verified=True,
    mesh_area_convergence_verified=True,
    residuals_verified=True,
    shape_delta_residuals_m=shape_delta_residuals,
    centerline_speed_delta_residuals=centerline_speed_delta_residuals,
    mesh_area_delta_residuals_m2=mesh_area_delta_residuals,
    maximum_normal_velocity_residuals=maximum_normal_velocity_residuals,
    refinement_convergence_verified=True,
    physical_closure_verified=True,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status=(
      'parameterized-planar-free-boundary-refinement-evidence; '
      'canonical-reflected-moc-closure-pending'
    ),
    message=(
      'independent parameterized planar free-boundary results are stable '
      'across the declared resolutions; this remains bounded potential-flow '
      'reference evidence and does not close the canonical reflected-MOC chain'
    ),
  )
####


def _free_boundary_area_ratio_measurement(mach: float, gamma: float) -> float:
  if (
    not isfinite(float(mach))
    or not isfinite(float(gamma))
    or gamma <= 1.0
    or mach <= 0.0
    or mach >= 1.0
  ):
    raise ValueError('free-boundary measurement requires a strict subsonic Mach')
  factor = 2.0 / (gamma + 1.0) * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  )
  return factor ** ((gamma + 1.0) / (2.0 * (gamma - 1.0))) / mach
####


def _free_boundary_mach_from_area_measurement(
  area_ratio: float,
  gamma: float,
) -> float:
  if not isfinite(float(area_ratio)) or area_ratio < 1.0:
    raise ValueError('free-boundary area ratio must be finite and at least one')
  lower = 1.0e-10
  upper = 1.0 - 1.0e-10
  for _ in range(80):
    midpoint = 0.5 * (lower + upper)
    if _free_boundary_area_ratio_measurement(midpoint, gamma) > area_ratio:
      lower = midpoint
    else:
      upper = midpoint
  return 0.5 * (lower + upper)
####


def _free_boundary_static_pressure_measurement(
  total_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  return total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
####


def _free_boundary_mass_flux_measurement(mach: float, gamma: float) -> float:
  return mach * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (-(gamma + 1.0) / (2.0 * (gamma - 1.0)))
####


def _free_boundary_line_angle_residual_measurement(
  flow_angle_rad: float,
  tangent_angle_rad: float,
) -> float:
  residual = (
    flow_angle_rad - tangent_angle_rad + 0.5 * pi
  ) % pi - 0.5 * pi
  return abs(residual)
####


def _free_boundary_segment_flow_angle_measurement(
  first_angle_rad: float,
  second_angle_rad: float,
) -> float:
  delta = (second_angle_rad - first_angle_rad + pi) % (2.0 * pi) - pi
  return first_angle_rad + 0.5 * delta
####


def _free_boundary_measurement_failure(
  status: MocMixedRegimeFreeBoundaryMeasurementStatus,
  *,
  result: MocMixedRegimeFreeBoundaryResult | None = None,
  topology: MocTopologyResult | None = None,
  request_verified: bool = False,
  perimeter_spec_verified: bool = False,
  boundary_verified: bool = False,
  downstream_condition_verified: bool = False,
  closure_verified: bool = False,
  field_model_verified: bool = False,
  field_layout_verified: bool = False,
  scalar_root_verified: bool = False,
  mass_flow_verified: bool = False,
  physical_closure_verified: bool = False,
  height_residual_m: float | None = None,
  pressure_residual_Pa: float | None = None,
  mass_flow_residual: float | None = None,
  free_boundary_pressure_residual_Pa: float | None = None,
  free_boundary_tangent_residual_rad: float | None = None,
  centerline_tangent_residual_rad: float | None = None,
  outlet_pressure_residual_Pa: float | None = None,
  free_boundary_geometry_residual_m: float | None = None,
  maximum_thermodynamic_residual: float | None = None,
  maximum_harmonic_residual: float | None = None,
  maximum_velocity_divergence_residual: float | None = None,
  control_section_verified: bool | None = None,
  control_section_flux_verified: bool | None = None,
  control_section_flux_residual: float | None = None,
  message: str,
) -> MocMixedRegimeFreeBoundaryMeasurement:
  field = None if result is None else result.field
  return MocMixedRegimeFreeBoundaryMeasurement(
    status=status,
    operator_id=MOC_MIXED_REGIME_FREE_BOUNDARY_OPERATOR_ID,
    model=None if result is None else result.model,
    solver_status=None if result is None else result.status.value,
    field_status=None if field is None else field.status.value,
    node_count=0 if field is None else len(field.nodes),
    cell_count=0 if field is None else len(field.cells),
    topology=_empty_topology() if topology is None else topology,
    ambient_pressure_Pa=None if result is None else result.ambient_pressure_Pa,
    target_outlet_height_m=None if result is None else result.target_outlet_height_m,
    outlet_height_m=None if result is None else result.outlet_height_m,
    ambient_mach=None if result is None else result.ambient_mach,
    outlet_mach=None if result is None else result.outlet_mach,
    request_verified=request_verified,
    perimeter_spec_verified=perimeter_spec_verified,
    boundary_verified=boundary_verified,
    downstream_condition_verified=downstream_condition_verified,
    closure_verified=closure_verified,
    field_model_verified=field_model_verified,
    field_layout_verified=field_layout_verified,
    scalar_root_verified=scalar_root_verified,
    mass_flow_verified=mass_flow_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    height_residual_m=height_residual_m,
    pressure_residual_Pa=pressure_residual_Pa,
    mass_flow_residual=mass_flow_residual,
    free_boundary_pressure_residual_Pa=free_boundary_pressure_residual_Pa,
    free_boundary_tangent_residual_rad=free_boundary_tangent_residual_rad,
    centerline_tangent_residual_rad=centerline_tangent_residual_rad,
    outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
    free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    control_section_verified=control_section_verified,
    control_section_flux_verified=control_section_flux_verified,
    control_section_flux_residual=control_section_flux_residual,
    claim_status=(
      'independent-solver-owned-quasi-1d-free-boundary-reference-measurement; '
      'not-canonical-moc-validation'
    ),
    message=message,
  )
####


def measure_mixed_regime_free_boundary_reference(
  result: MocMixedRegimeFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-9,
  pressure_tolerance: float = 1.0e-8,
  normal_flux_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 1.0e-8,
  height_tolerance_m: float = 1.0e-9,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  mass_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocMixedRegimeFreeBoundaryMeasurement:
  """Independently measure the solver-owned quasi-1D free-boundary lane.

  This operator consumes the returned result as data.  It recomputes the
  outlet-height relation from the terminal total state, checks the generated
  perimeter and selected free-boundary condition, and remeasures the scalar
  radial field.  The reported two-dimensional velocity-divergence residual is
  diagnostic only because this reference is not a two-dimensional flow solve.
  """

  if not isinstance(result, MocMixedRegimeFreeBoundaryResult):
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.INVALID_INPUT,
      message='result must be a MocMixedRegimeFreeBoundaryResult',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('normal_flux_tolerance', normal_flux_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('height_tolerance_m', height_tolerance_m),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('mass_tolerance', mass_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  expected_model = 'solver-owned-quasi-1d-ambient-free-boundary-reference'
  expected_field_model = 'solver-owned-subsonic-free-boundary-reference'
  supported_result_models = {
    expected_field_model,
    'solver-owned-control-section-quasi-1d-reference',
    'solver-owned-control-section-flux-quasi-1d-reference',
  }
  if result.model not in supported_result_models:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.INVALID_INPUT,
      result=result,
      message=(
        'free-boundary measurement requires an explicitly named supported '
        'quasi-one-dimensional result model, '
        f'received {result.model!r}'
      ),
    )
  integrated_flux_mode = (
    result.model == 'solver-owned-control-section-flux-quasi-1d-reference'
  )
  control_section_verified: bool | None = None
  control_section_flux_verified: bool | None = None
  control_section_flux_residual: float | None = None
  field = result.field
  boundary = result.boundary
  specification = result.perimeter_spec
  condition = result.downstream_condition
  closure = result.closure
  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      result=result,
      message='free-boundary result did not retain its scalar boundary',
    )
  if not isinstance(field, MocMixedRegimeFieldResult):
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.FIELD_FAILURE,
      result=result,
      boundary_verified=False,
      message='free-boundary result did not retain a scalar field',
    )
  if not isinstance(specification, MocMixedRegimeDownstreamPerimeterSpec):
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      message='free-boundary result did not retain its generated perimeter specification',
    )
  request = result.request
  if result.control_section is not None:
    try:
      independent_control_section = validate_mixed_regime_control_section(
        request,
        result.control_section,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
        pressure_tolerance=pressure_tolerance,
        normal_flux_tolerance=normal_flux_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _free_boundary_measurement_failure(
        MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
        result=result,
        control_section_verified=False,
        control_section_flux_verified=(False if integrated_flux_mode else None),
        message=f'control section could not be independently remeasured: {error}',
      )
    cached_control_section_verified = bool(
      result.control_section_validation == independent_control_section
    )
    control_section_verified = bool(
      cached_control_section_verified and independent_control_section.converged
    )
    if integrated_flux_mode:
      upstream_state = request.terminal.upstream_state
      if (
        upstream_state is None
        or result.control_section_validation is None
        or independent_control_section.mass_flux_proxy is None
      ):
        return _free_boundary_measurement_failure(
          MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
          result=result,
          control_section_verified=False,
          control_section_flux_verified=False,
          message=(
            'integrated-flux free-boundary result did not retain the terminal '
            'gamma or its control-section validation'
          ),
        )
      terminal_flux = request.terminal_downstream_total_pressure_Pa * (
        _free_boundary_mass_flux_measurement(
          request.terminal_downstream_mach,
          upstream_state.gamma,
        )
      )
      expected_height = independent_control_section.mass_flux_proxy / terminal_flux
      height_identity_residual = abs(
        result.effective_inlet_height_m * terminal_flux
        - independent_control_section.mass_flux_proxy
      ) / max(1.0, abs(independent_control_section.mass_flux_proxy))
      stored_height = result.control_section_flux_equivalent_height_m
      stored_proxy = result.control_section_flux_proxy
      stored_residual = result.control_section_flux_residual
      control_section_flux_residual = height_identity_residual
      control_section_flux_verified = bool(
        control_section_verified
        and not result.control_section_projection_verified
        and stored_proxy is not None
        and abs(stored_proxy - independent_control_section.mass_flux_proxy)
        <= mass_tolerance * max(1.0, abs(independent_control_section.mass_flux_proxy))
        and stored_height is not None
        and abs(stored_height - expected_height) <= height_tolerance_m
        and height_identity_residual <= mass_tolerance
        and stored_residual is not None
        and abs(stored_residual - height_identity_residual) <= mass_tolerance
        and result.control_section_flux_verified
      )
    else:
      control_section_verified = bool(
        control_section_verified
        and result.control_section_projection_verified
        and independent_control_section.maximum_terminal_state_residual is not None
        and independent_control_section.maximum_terminal_state_residual
        <= state_tolerance
      )
  elif integrated_flux_mode:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      result=result,
      control_section_verified=False,
      control_section_flux_verified=False,
      message='integrated-flux free-boundary result did not retain its control section',
    )
  request_verified = bool(
    field.boundary == boundary
    and boundary.terminal == request.terminal
    and boundary.supersonic_patch == request.supersonic_patch
    and boundary.supersonic_patch_sample_count == len(request.supersonic_patch)
  )
  if not request_verified:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      result=result,
      request_verified=False,
      message='free-boundary field does not retain the exact requested terminal seam',
    )
  try:
    independent_boundary = validate_mixed_regime_boundary(
      request.terminal,
      request.supersonic_patch,
      supersonic_patch_converged=True,
      subsonic_samples=boundary.subsonic_samples,
      perimeter_points_m=boundary.perimeter_points_m,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      result=result,
      request_verified=request_verified,
      message=f'free-boundary scalar seam could not be remeasured: {error}',
    )
  boundary_verified = independent_boundary.converged
  if not boundary_verified:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      result=result,
      request_verified=request_verified,
      boundary_verified=False,
      message=(
        'free-boundary scalar seam failed independent measurement: '
        f'{independent_boundary.message}'
      ),
    )
  pressure_scale = max(1.0, abs(result.ambient_pressure_Pa))
  perimeter_spec_verified = bool(
    specification.model == expected_model
    and specification.condition_kind is (
      MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY
    )
    and specification.perimeter_points_m == boundary.perimeter_points_m
    and specification.ambient_pressure_Pa is not None
    and abs(specification.ambient_pressure_Pa - result.ambient_pressure_Pa)
    <= pressure_tolerance * pressure_scale
    and bool(specification.condition_edge_indices)
    and bool(specification.condition_sample_indices)
  )
  if not perimeter_spec_verified:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      result=result,
      request_verified=request_verified,
      boundary_verified=boundary_verified,
      message='free-boundary perimeter specification does not match the returned boundary',
    )
  try:
    independent_condition = validate_mixed_regime_downstream_condition(
      independent_boundary,
      specification.condition_kind,
      ambient_pressure_Pa=specification.ambient_pressure_Pa,
      condition_edge_indices=specification.condition_edge_indices,
      condition_sample_indices=specification.condition_sample_indices,
      position_tolerance_m=position_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      result=result,
      request_verified=request_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      boundary_verified=boundary_verified,
      message=f'free-boundary condition could not be remeasured: {error}',
    )
  downstream_condition_verified = bool(
    isinstance(condition, MocMixedRegimeDownstreamConditionResult)
    and condition.boundary == boundary
    and condition.converged
    and field.downstream_condition == condition
    and independent_condition.converged
  )
  if not downstream_condition_verified:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.CONDITION_FAILURE,
      result=result,
      request_verified=request_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      boundary_verified=boundary_verified,
      downstream_condition_verified=False,
      free_boundary_pressure_residual_Pa=independent_condition.maximum_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=independent_condition.maximum_tangent_residual_rad,
      message='free-boundary condition did not pass independent condition measurement',
    )

  points = boundary.perimeter_points_m
  samples = boundary.subsonic_samples
  sample_indices = specification.condition_sample_indices
  x0, y0 = request.terminal_point_m
  height_residual_m: float | None = None
  pressure_residual_Pa: float | None = None
  mass_flow_residual: float | None = None
  scalar_root_verified = False
  mass_flow_verified = False
  centerline_tangent_residual_rad: float | None = None
  outlet_pressure_residual_Pa: float | None = None
  free_boundary_geometry_residual_m: float | None = None
  try:
    upstream_state = request.terminal.upstream_state
    if not isinstance(upstream_state, CharacteristicState):
      raise ValueError('terminal upstream state is not a CharacteristicState')
    gamma = upstream_state.gamma
    total_pressure = request.terminal_downstream_total_pressure_Pa
    ambient_mach_squared = 2.0 / (gamma - 1.0) * (
      (total_pressure / result.ambient_pressure_Pa) ** ((gamma - 1.0) / gamma)
      - 1.0
    )
    ambient_mach = sqrt(ambient_mach_squared)
    terminal_area_ratio = _free_boundary_area_ratio_measurement(
      request.terminal_downstream_mach,
      gamma,
    )
    ambient_area_ratio = _free_boundary_area_ratio_measurement(
      ambient_mach,
      gamma,
    )
    expected_target_height = (
      result.effective_inlet_height_m
      * ambient_area_ratio
      / terminal_area_ratio
    )
    if result.target_outlet_height_m is None or result.outlet_height_m is None:
      raise ValueError('free-boundary result did not retain its outlet height')
    height_residual_m = abs(
      result.target_outlet_height_m - expected_target_height
    )
    outlet_area_ratio = terminal_area_ratio * (
      result.outlet_height_m / result.effective_inlet_height_m
    )
    expected_outlet_mach = _free_boundary_mach_from_area_measurement(
      outlet_area_ratio,
      gamma,
    )
    expected_outlet_pressure = _free_boundary_static_pressure_measurement(
      total_pressure,
      expected_outlet_mach,
      gamma,
    )
    pressure_residual_Pa = abs(
      expected_outlet_pressure - result.ambient_pressure_Pa
    )
    pressure_report_residual = result.pressure_residual_Pa
    root_report_consistent = (
      pressure_report_residual is not None
      and abs(pressure_report_residual - pressure_residual_Pa)
      <= pressure_tolerance * pressure_scale
      and result.ambient_mach is not None
      and abs(result.ambient_mach - ambient_mach) <= state_tolerance
      and result.outlet_mach is not None
      and abs(result.outlet_mach - expected_outlet_mach) <= state_tolerance
    )
    scalar_root_verified = bool(
      height_residual_m <= height_tolerance_m
      and pressure_residual_Pa <= pressure_tolerance * pressure_scale
      and root_report_consistent
    )
    terminal_mass = result.effective_inlet_height_m * (
      _free_boundary_mass_flux_measurement(
        request.terminal_downstream_mach,
        gamma,
      )
    )
    outlet_mass = result.outlet_height_m * (
      _free_boundary_mass_flux_measurement(expected_outlet_mach, gamma)
    )
    mass_flow_residual = abs(outlet_mass - terminal_mass) / max(
      1.0,
      abs(terminal_mass),
    )
    mass_report_consistent = (
      result.mass_flow_residual is not None
      and abs(result.mass_flow_residual - mass_flow_residual) <= mass_tolerance
    )
    mass_flow_verified = bool(
      mass_flow_residual <= mass_tolerance and mass_report_consistent
    )
    centerline_tangent_residual_rad = _free_boundary_line_angle_residual_measurement(
      _free_boundary_segment_flow_angle_measurement(
        samples[0].flow_angle_rad,
        samples[1].flow_angle_rad,
      ),
      atan2(
        points[1][1] - points[0][1],
        points[1][0] - points[0][0],
      ),
    )
    outlet_pressure_residual_Pa = max(
      abs(samples[index].static_pressure_Pa - result.ambient_pressure_Pa)
      for index in (1, sample_indices[0])
    )
    if result.outlet_height_m <= 0.0:
      raise ValueError('free-boundary result returned a nonpositive outlet height')
    expected_centerline = (x0 + result.downstream_length_m, y0)
    expected_outer = (
      expected_centerline[0],
      y0 + result.outlet_height_m,
    )
    geometry_residuals = [
      hypot(points[1][0] - expected_centerline[0], points[1][1] - expected_centerline[1]),
      hypot(points[2][0] - expected_outer[0], points[2][1] - expected_outer[1]),
    ]
    geometry_scale = max(
      1.0,
      abs(result.downstream_length_m),
      abs(result.outlet_height_m),
    )
    for index in sample_indices:
      point = points[index]
      geometry_residuals.append(
        abs(
          (point[1] - y0) * result.downstream_length_m
          - (point[0] - x0) * result.outlet_height_m
        ) / geometry_scale
      )
    free_boundary_geometry_residual_m = max(geometry_residuals)
  except (ArithmeticError, FloatingPointError, IndexError, TypeError, ValueError):
    scalar_root_verified = False
    mass_flow_verified = False

  try:
    topology = validate_moc_mesh(
      field.cells,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    maximum_thermodynamic_residual = _mixed_field_thermodynamic_residual(
      field.nodes,
    )
    maximum_harmonic_residual = _mixed_field_harmonic_residual(
      field,
      position_tolerance_m=position_tolerance_m,
    )
    maximum_velocity_divergence_residual = _mixed_field_velocity_divergence_residual(
      field,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    topology = _empty_topology()
    maximum_thermodynamic_residual = None
    maximum_harmonic_residual = None
    maximum_velocity_divergence_residual = None
  finite_nodes = all(
    isinstance(sample, MocMixedRegimeFieldSample)
    and all(isfinite(float(value)) for value in (
      *sample.point_m,
      sample.mach,
      sample.flow_angle_rad,
      sample.static_pressure_Pa,
      sample.total_pressure_Pa,
      sample.gamma,
    ))
    for sample in field.nodes
  )
  expected_node_count = 1 + field.radial_divisions * max(
    0,
    len(boundary.perimeter_points_m) - 1,
  )
  field_layout_verified = bool(
    len(field.nodes) == expected_node_count
    and field.interior_point_m is not None
    and maximum_harmonic_residual is not None
  )
  field_model_verified = bool(
    field.model == expected_field_model
    and field.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD
    and field.boundary == boundary
    and finite_nodes
    and len(field.nodes) > 0
    and len(field.cells) > 0
    and topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
    and maximum_thermodynamic_residual is not None
    and maximum_thermodynamic_residual <= thermodynamic_tolerance
    and maximum_harmonic_residual is not None
    and maximum_harmonic_residual <= residual_tolerance
  )
  geometry_verified = (
    free_boundary_geometry_residual_m is not None
    and free_boundary_geometry_residual_m <= position_tolerance_m
  )
  condition_residuals_verified = bool(
    independent_condition.maximum_pressure_residual_Pa is not None
    and independent_condition.maximum_pressure_residual_Pa
    <= pressure_tolerance * pressure_scale
    and independent_condition.maximum_tangent_residual_rad is not None
    and independent_condition.maximum_tangent_residual_rad
    <= tangent_tolerance_rad
    and centerline_tangent_residual_rad is not None
    and centerline_tangent_residual_rad <= tangent_tolerance_rad
    and outlet_pressure_residual_Pa is not None
    and outlet_pressure_residual_Pa <= pressure_tolerance * pressure_scale
  )
  closure_verified = bool(
    isinstance(closure, MocMixedRegimeClosureResult)
    and closure.converged
    and closure.request == request
    and closure.field == field
  )
  control_section_gate_verified = bool(
    control_section_verified is not False
    and (
      not integrated_flux_mode
      or control_section_flux_verified is True
    )
  )
  physical_closure_verified = bool(
    request_verified
    and perimeter_spec_verified
    and boundary_verified
    and downstream_condition_verified
    and closure_verified
    and field_model_verified
    and field_layout_verified
    and scalar_root_verified
    and mass_flow_verified
    and geometry_verified
    and condition_residuals_verified
    and control_section_gate_verified
  )
  if not physical_closure_verified:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.RESIDUAL_FAILURE,
      result=result,
      topology=topology,
      request_verified=request_verified,
      perimeter_spec_verified=perimeter_spec_verified,
      boundary_verified=boundary_verified,
      downstream_condition_verified=downstream_condition_verified,
      closure_verified=closure_verified,
      field_model_verified=field_model_verified,
      field_layout_verified=field_layout_verified,
      scalar_root_verified=scalar_root_verified,
      mass_flow_verified=mass_flow_verified,
      height_residual_m=height_residual_m,
      pressure_residual_Pa=pressure_residual_Pa,
      mass_flow_residual=mass_flow_residual,
      free_boundary_pressure_residual_Pa=independent_condition.maximum_pressure_residual_Pa,
      free_boundary_tangent_residual_rad=independent_condition.maximum_tangent_residual_rad,
      centerline_tangent_residual_rad=centerline_tangent_residual_rad,
      outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
      free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
      maximum_thermodynamic_residual=maximum_thermodynamic_residual,
      maximum_harmonic_residual=maximum_harmonic_residual,
      maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
      control_section_verified=control_section_verified,
      control_section_flux_verified=control_section_flux_verified,
      control_section_flux_residual=control_section_flux_residual,
      message=(
        'independent free-boundary reference gates failed: '
        f'field_model={field_model_verified}, root={scalar_root_verified}, '
        f'mass={mass_flow_verified}, geometry={geometry_verified}, '
        f'condition_residuals={condition_residuals_verified}'
      ),
    )
  return _free_boundary_measurement_failure(
    MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED,
    result=result,
    topology=topology,
    request_verified=request_verified,
    perimeter_spec_verified=perimeter_spec_verified,
    boundary_verified=boundary_verified,
    downstream_condition_verified=downstream_condition_verified,
    closure_verified=closure_verified,
    field_model_verified=field_model_verified,
    field_layout_verified=field_layout_verified,
    scalar_root_verified=scalar_root_verified,
    mass_flow_verified=mass_flow_verified,
    physical_closure_verified=True,
    height_residual_m=height_residual_m,
    pressure_residual_Pa=pressure_residual_Pa,
    mass_flow_residual=mass_flow_residual,
    free_boundary_pressure_residual_Pa=independent_condition.maximum_pressure_residual_Pa,
    free_boundary_tangent_residual_rad=independent_condition.maximum_tangent_residual_rad,
    centerline_tangent_residual_rad=centerline_tangent_residual_rad,
    outlet_pressure_residual_Pa=outlet_pressure_residual_Pa,
    free_boundary_geometry_residual_m=free_boundary_geometry_residual_m,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    control_section_verified=control_section_verified,
    control_section_flux_verified=control_section_flux_verified,
    control_section_flux_residual=control_section_flux_residual,
    message=(
      'independent quasi-one-dimensional free-boundary reference measurement '
      'passed its exact seam, generated-perimeter, condition, radial-field, '
      'height-root, and mass-flow gates; it remains non-canonical evidence'
    ),
  )
####


def _free_boundary_refinement_failure(
  status: MocMixedRegimeFreeBoundaryRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocMixedRegimeFreeBoundaryRefinementCase] = (),
  measurements: Sequence[MocMixedRegimeFreeBoundaryMeasurement] = (),
  resolution_order_verified: bool = False,
  request_consistent: bool = False,
  solver_parameters_consistent: bool = False,
  perimeter_resolution_verified: bool = False,
  radial_divisions_consistent: bool = False,
  case_measurements_verified: bool = False,
  scalar_root_verified: bool = False,
  mass_flow_verified: bool = False,
  geometry_verified: bool = False,
  local_reference_closure_verified: bool = False,
  refinement_convergence_verified: bool = False,
  outlet_height_delta_residuals_m: Sequence[float] = (),
  height_root_residuals_m: Sequence[float | None] = (),
  free_boundary_geometry_residuals_m: Sequence[float | None] = (),
  mass_flow_residuals: Sequence[float | None] = (),
  maximum_velocity_divergence_residuals: Sequence[float | None] = (),
) -> MocMixedRegimeFreeBoundaryRefinementMeasurement:
  valid_cases = tuple(
    case
    for case in cases
    if isinstance(case, MocMixedRegimeFreeBoundaryRefinementCase)
  )
  valid_measurements = tuple(
    measurement
    for measurement in measurements
    if isinstance(measurement, MocMixedRegimeFreeBoundaryMeasurement)
  )
  paired_count = min(len(valid_cases), len(valid_measurements))
  return MocMixedRegimeFreeBoundaryRefinementMeasurement(
    status=status,
    cases=valid_cases[:paired_count],
    measurements=valid_measurements[:paired_count],
    resolution_order_verified=resolution_order_verified,
    request_consistent=request_consistent,
    solver_parameters_consistent=solver_parameters_consistent,
    perimeter_resolution_verified=perimeter_resolution_verified,
    radial_divisions_consistent=radial_divisions_consistent,
    case_measurements_verified=case_measurements_verified,
    scalar_root_verified=scalar_root_verified,
    mass_flow_verified=mass_flow_verified,
    geometry_verified=geometry_verified,
    local_reference_closure_verified=local_reference_closure_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    outlet_height_delta_residuals_m=tuple(outlet_height_delta_residuals_m),
    height_root_residuals_m=tuple(height_root_residuals_m),
    free_boundary_geometry_residuals_m=tuple(
      free_boundary_geometry_residuals_m
    ),
    mass_flow_residuals=tuple(mass_flow_residuals),
    maximum_velocity_divergence_residuals=tuple(
      maximum_velocity_divergence_residuals
    ),
    message=message,
  )
####


def measure_mixed_regime_free_boundary_refinement(
  cases: Sequence[MocMixedRegimeFreeBoundaryRefinementCase],
  *,
  outlet_height_tolerance_m: float = 1.0e-8,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-9,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 1.0e-8,
  height_tolerance_m: float = 1.0e-9,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-8,
  mass_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocMixedRegimeFreeBoundaryRefinementMeasurement:
  """Compare independently measured free-boundary results by resolution.

  The operator reruns the single-case measurement for every supplied result,
  verifies that the exact terminal request and solver parameters are held
  fixed, and compares the returned outlet height between successive
  resolutions.  It measures numerical stability of the quasi-one-dimensional
  reference only; a passing sequence does not close the canonical reflected
  two-dimensional downstream problem.
  """

  for name, value in (
    ('outlet_height_tolerance_m', outlet_height_tolerance_m),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance_rad', tangent_tolerance_rad),
    ('height_tolerance_m', height_tolerance_m),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('mass_tolerance', mass_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    items = tuple(cases)
  except TypeError:
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  if len(items) < 2:
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'at least two free-boundary refinement cases are required',
    )
  if any(
    not isinstance(case, MocMixedRegimeFreeBoundaryRefinementCase)
    for case in items
  ):
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain '
      'MocMixedRegimeFreeBoundaryRefinementCase values',
      cases=items,
    )
  resolutions = tuple(case.resolution for case in items)
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
      cases=items,
    )

  measurements = tuple(
    measure_mixed_regime_free_boundary_reference(
      case.result,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance_rad=tangent_tolerance_rad,
      height_tolerance_m=height_tolerance_m,
      thermodynamic_tolerance=thermodynamic_tolerance,
      residual_tolerance=residual_tolerance,
      mass_tolerance=mass_tolerance,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for case in items
  )
  case_measurements_verified = all(
    measurement.converged for measurement in measurements
  )
  scalar_root_verified = all(
    measurement.scalar_root_verified for measurement in measurements
  )
  mass_flow_verified = all(
    measurement.mass_flow_verified for measurement in measurements
  )
  height_root_residuals = tuple(
    measurement.height_residual_m for measurement in measurements
  )
  mass_flow_residuals = tuple(
    measurement.mass_flow_residual for measurement in measurements
  )
  geometry_residuals = tuple(
    measurement.free_boundary_geometry_residual_m
    for measurement in measurements
  )
  velocity_divergence_residuals = tuple(
    measurement.maximum_velocity_divergence_residual
    for measurement in measurements
  )
  geometry_verified = all(
    residual is not None and residual <= float(position_tolerance_m)
    for residual in geometry_residuals
  )
  local_reference_closure_verified = all(
    measurement.physical_closure_verified
    and measurement.chain_promotion_blocked
    and not measurement.production_claim_allowed
    for measurement in measurements
  )

  results = tuple(case.result for case in items)
  request_consistent = all(
    result.request == results[0].request
    for result in results[1:]
  )

  def _consistent_float(values: Sequence[float]) -> bool:
    if not values:
      return False
    reference = float(values[0])
    return all(
      abs(float(value) - reference)
      <= 1.0e-12 * max(1.0, abs(float(value)), abs(reference))
      for value in values[1:]
    )

  models = tuple(result.model for result in results)
  ambient_pressures = tuple(result.ambient_pressure_Pa for result in results)
  inlet_heights = tuple(result.effective_inlet_height_m for result in results)
  downstream_lengths = tuple(result.downstream_length_m for result in results)
  radial_values = tuple(
    0 if result.field is None else result.field.radial_divisions
    for result in results
  )
  solver_parameters_consistent = bool(
    len(set(models)) == 1
    and _consistent_float(ambient_pressures)
    and _consistent_float(inlet_heights)
    and _consistent_float(downstream_lengths)
  )
  perimeter_counts = tuple(
    0
    if result.boundary is None
    else len(result.boundary.perimeter_points_m)
    for result in results
  )
  perimeter_resolution_verified = bool(
    all(count >= 3 for count in perimeter_counts)
    and all(
      right > left
      for left, right in zip(perimeter_counts, perimeter_counts[1:])
    )
  )
  radial_divisions_consistent = bool(
    all(value > 0 for value in radial_values)
    and len(set(radial_values)) == 1
  )

  outlet_heights = tuple(
    measurement.outlet_height_m for measurement in measurements
  )
  if all(height is not None for height in outlet_heights):
    resolved_outlet_heights = tuple(
      height for height in outlet_heights if height is not None
    )
    outlet_height_delta_residuals = tuple(
      abs(current - previous)
      for previous, current in zip(
        resolved_outlet_heights,
        resolved_outlet_heights[1:],
      )
    )
  else:
    outlet_height_delta_residuals = ()
  refinement_convergence_verified = bool(
    case_measurements_verified
    and scalar_root_verified
    and mass_flow_verified
    and geometry_verified
    and local_reference_closure_verified
    and len(outlet_height_delta_residuals) == len(items) - 1
    and all(
      residual <= float(outlet_height_tolerance_m)
      for residual in outlet_height_delta_residuals
    )
  )

  common = {
    'cases': items,
    'measurements': measurements,
    'resolution_order_verified': True,
    'request_consistent': request_consistent,
    'solver_parameters_consistent': solver_parameters_consistent,
    'perimeter_resolution_verified': perimeter_resolution_verified,
    'radial_divisions_consistent': radial_divisions_consistent,
    'case_measurements_verified': case_measurements_verified,
    'scalar_root_verified': scalar_root_verified,
    'mass_flow_verified': mass_flow_verified,
    'geometry_verified': geometry_verified,
    'local_reference_closure_verified': local_reference_closure_verified,
    'refinement_convergence_verified': refinement_convergence_verified,
    'outlet_height_delta_residuals_m': outlet_height_delta_residuals,
    'height_root_residuals_m': height_root_residuals,
    'free_boundary_geometry_residuals_m': geometry_residuals,
    'mass_flow_residuals': mass_flow_residuals,
    'maximum_velocity_divergence_residuals': velocity_divergence_residuals,
  }
  if not case_measurements_verified:
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CASE_FAILURE,
      'one or more free-boundary cases failed independent measurement',
      **common,
    )
  if not (
    request_consistent
    and solver_parameters_consistent
    and perimeter_resolution_verified
    and radial_divisions_consistent
  ):
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'refinement cases must retain one exact seam and fixed solver parameters '
      'while increasing the returned perimeter resolution',
      **common,
    )
  if not refinement_convergence_verified:
    return _free_boundary_refinement_failure(
      MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.SENSITIVITY_FAILURE,
      'free-boundary outlet height or local reference residuals exceeded the '
      'declared refinement tolerances',
      **common,
    )
  return MocMixedRegimeFreeBoundaryRefinementMeasurement(
    status=MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CONVERGED,
    cases=items,
    measurements=measurements,
    resolution_order_verified=True,
    request_consistent=True,
    solver_parameters_consistent=True,
    perimeter_resolution_verified=True,
    radial_divisions_consistent=True,
    case_measurements_verified=True,
    scalar_root_verified=True,
    mass_flow_verified=True,
    geometry_verified=True,
    local_reference_closure_verified=True,
    refinement_convergence_verified=True,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    outlet_height_delta_residuals_m=outlet_height_delta_residuals,
    height_root_residuals_m=height_root_residuals,
    free_boundary_geometry_residuals_m=geometry_residuals,
    mass_flow_residuals=mass_flow_residuals,
    maximum_velocity_divergence_residuals=velocity_divergence_residuals,
    message=(
      'independent solver-owned quasi-one-dimensional free-boundary results '
      'are stable across the declared resolutions; this is refinement evidence '
      'only and does not close or promote the canonical reflected-MOC chain'
    ),
  )
####


def _terminal_shock_x_at_y(
  shock_points: Sequence[Point],
  ordinate: float,
  *,
  position_tolerance_m: float,
) -> float | None:
  for first, second in zip(shock_points, shock_points[1:]):
    low = min(first[1], second[1])
    high = max(first[1], second[1])
    if low - position_tolerance_m <= ordinate <= high + position_tolerance_m:
      if abs(second[1] - first[1]) <= position_tolerance_m:
        return 0.5 * (first[0] + second[0])
      fraction = (ordinate - first[1]) / (second[1] - first[1])
      return first[0] + fraction * (second[0] - first[0])
  return None
####


def _terminal_shock_coverage(
  cells: Sequence[object],
  shock_points: Sequence[Point],
  *,
  position_tolerance_m: float,
  mesh_vertex_tolerance_m: float,
) -> tuple[int, bool, float | None]:
  """Measure coverage of a sampled shock over explicit mesh perimeter edges."""

  if len(shock_points) < 2:
    return 0, False, None
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  edge_points: dict[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[Point, Point],
  ] = {}
  for cell in cells:
    vertices = _cell_vertices(cell)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      first_key = _key(first, mesh_vertex_tolerance_m)
      second_key = _key(second, mesh_vertex_tolerance_m)
      edge = (
        (first_key, second_key)
        if first_key <= second_key
        else (second_key, first_key)
      )
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
      edge_points.setdefault(edge, (first, second))
  target_low = min(point[1] for point in shock_points)
  target_high = max(point[1] for point in shock_points)
  covered_edges: list[tuple[float, float]] = []
  residuals: list[float] = []
  for edge, count in edge_counts.items():
    if count != 1:
      continue
    first, second = edge_points[edge]
    low = min(first[1], second[1])
    high = max(first[1], second[1])
    if high < target_low - position_tolerance_m or low > target_high + position_tolerance_m:
      continue
    ordinates = [
      first[1],
      second[1],
      *(
        point[1]
        for point in shock_points
        if low - position_tolerance_m <= point[1] <= high + position_tolerance_m
      ),
    ]
    edge_residual = 0.0
    for ordinate in ordinates:
      if abs(second[1] - first[1]) <= mesh_vertex_tolerance_m:
        edge_x = 0.5 * (first[0] + second[0])
      else:
        fraction = (ordinate - first[1]) / (second[1] - first[1])
        edge_x = first[0] + fraction * (second[0] - first[0])
      shock_x = _terminal_shock_x_at_y(
        shock_points,
        ordinate,
        position_tolerance_m=position_tolerance_m,
      )
      if shock_x is None:
        edge_residual = float('inf')
        break
      edge_residual = max(edge_residual, abs(edge_x - shock_x))
    if edge_residual <= position_tolerance_m:
      covered_edges.append((low, high))
      residuals.append(edge_residual)
  covered_edges.sort()
  merged: list[tuple[float, float]] = []
  for low, high in covered_edges:
    if merged and low <= merged[-1][1] + position_tolerance_m:
      merged[-1] = (merged[-1][0], max(merged[-1][1], high))
    else:
      merged.append((low, high))
  covered = bool(merged) and (
    merged[0][0] <= target_low + position_tolerance_m
    and merged[-1][1] >= target_high - position_tolerance_m
    and all(
      second[0] <= first[1] + position_tolerance_m
      for first, second in zip(merged, merged[1:])
    )
  )
  return len(covered_edges), covered, max(residuals, default=None)
####


def measure_moc_terminal_closure(
  observation: MocTerminalClosureObservation,
  *,
  position_tolerance_m: float = 1.0e-9,
  axis_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  potential_residual_tolerance: float = 1.0e-8,
  potential_velocity_tolerance: float = 1.0e-8,
  potential_circulation_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocTerminalClosureMeasurement:
  """Measure a terminal field and optional mixed-regime attachment.

  This operator intentionally re-runs geometry, topology, shock pressure-loss,
  scalar seam, reference-field residual, and downstream-condition checks.  It
  never infers a missing perimeter and never turns a passing terminal result
  into a continued supersonic cell.
  """

  if not isinstance(observation, MocTerminalClosureObservation):
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      message='observation must be a MocTerminalClosureObservation',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
    ('potential_residual_tolerance', potential_residual_tolerance),
    ('potential_velocity_tolerance', potential_velocity_tolerance),
    ('potential_circulation_tolerance', potential_circulation_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  field = observation.terminal_field
  if not isinstance(field, MocTerminalShockCellFieldResult):
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      message='terminal_field must be a MocTerminalShockCellFieldResult',
    )
  terminal_field_status = field.status.value
  closure = observation.mixed_regime_closure
  mixed_regime_status = (
    None
    if closure is None
    else closure.status.value
    if isinstance(closure, MocMixedRegimeClosureResult)
    else 'invalid_input'
  )
  try:
    supersonic_topology = validate_moc_mesh(
      field.cells,
      vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.INVALID_INPUT,
      terminal_field_status=terminal_field_status,
      mixed_regime_status=mixed_regime_status,
      message=f'terminal supersonic mesh could not be measured: {error}',
    )
  supersonic_node_count = len(field.nodes)
  supersonic_cell_count = len(field.cells)
  try:
    shock_points = _points(
      field.terminal_shock_boundary_points_m,
      'terminal shock boundary',
    )
  except ValueError as error:
    return _terminal_measurement_failure(
      MocTerminalClosureMeasurementStatus.GEOMETRY_FAILURE,
      terminal_field_status=terminal_field_status,
      mixed_regime_status=mixed_regime_status,
      supersonic_topology=supersonic_topology,
      supersonic_node_count=supersonic_node_count,
      supersonic_cell_count=supersonic_cell_count,
      message=str(error),
    )
  try:
    terminal_shock_edge_count, shock_boundary_edges_verified, _shock_residual = (
      _terminal_shock_coverage(
        field.cells,
        shock_points,
        position_tolerance_m=position_tolerance_m,
        mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
    )
  except (AttributeError, TypeError, ValueError) as error:
    shock_boundary_edges_verified = False
    terminal_shock_edge_count = 0
    edge_error = str(error)
  else:
    edge_error = ''
  terminal = field.terminal_normal_shock
  terminal_normal_shock_verified = False
  terminal_ratio: float | None = None
  terminal_upstream_total: float | None = None
  if isinstance(terminal, MocNormalShockTerminalResult):
    terminal_values = (
      terminal.shock_point_m,
      terminal.upstream_state,
      terminal.upstream_pressure_Pa,
      terminal.downstream_flow_angle_rad,
      terminal.downstream_mach,
      terminal.downstream_pressure_Pa,
      terminal.upstream_total_pressure_Pa,
      terminal.downstream_total_pressure_Pa,
      terminal.total_pressure_ratio,
    )
    if all(value is not None for value in terminal_values):
      assert terminal.shock_point_m is not None
      assert terminal.upstream_state is not None
      assert terminal.upstream_pressure_Pa is not None
      assert terminal.downstream_flow_angle_rad is not None
      assert terminal.downstream_mach is not None
      assert terminal.downstream_pressure_Pa is not None
      assert terminal.upstream_total_pressure_Pa is not None
      assert terminal.downstream_total_pressure_Pa is not None
      assert terminal.total_pressure_ratio is not None
      terminal_upstream_total = _state_total_pressure(
        terminal.upstream_state,
        terminal.upstream_pressure_Pa,
      )
      terminal_ratio = (
        terminal.downstream_total_pressure_Pa / terminal_upstream_total
      )
      terminal_scalar_values = (
        terminal.shock_point_m[0],
        terminal.shock_point_m[1],
        terminal.upstream_pressure_Pa,
        terminal.downstream_flow_angle_rad,
        terminal.downstream_mach,
        terminal.downstream_pressure_Pa,
        terminal.upstream_total_pressure_Pa,
        terminal.downstream_total_pressure_Pa,
        terminal.total_pressure_ratio,
      )
      terminal_normal_shock_verified = bool(
        terminal.converged
        and terminal.subsonic
        and all(isfinite(float(value)) for value in terminal_scalar_values)
        and terminal.downstream_mach > 0.0
        and terminal.downstream_pressure_Pa > 0.0
        and terminal.upstream_total_pressure_Pa > 0.0
        and terminal.downstream_total_pressure_Pa > 0.0
        and 0.0 < terminal.total_pressure_ratio < 1.0
        and _relative_value_residual(
          terminal_upstream_total,
          terminal.upstream_total_pressure_Pa,
        ) <= pressure_tolerance
        and _relative_value_residual(
          terminal_ratio,
          terminal.total_pressure_ratio,
        ) <= pressure_tolerance
        and hypot(
          terminal.shock_point_m[0] - shock_points[-1][0],
          terminal.shock_point_m[1] - shock_points[-1][1],
        ) <= position_tolerance_m
      )
  upstream_states = field.terminal_shock_upstream_states
  upstream_pressures = field.terminal_shock_upstream_pressure_Pa
  patch = field.terminal_shock_supersonic_downstream_states
  terminal_shock_geometry_verified = bool(
    len(upstream_states) == len(shock_points)
    and len(upstream_pressures) == len(shock_points)
    and len(patch) == len(shock_points) - 1
    and shock_boundary_edges_verified
    and abs(shock_points[-1][1]) <= axis_tolerance_m
    and all(
      isinstance(state, CharacteristicState)
      and hypot(
        state.x_m - point[0],
        state.y_m - point[1],
      ) <= state_tolerance
      for state, point in zip(upstream_states, shock_points, strict=True)
    )
    and all(
      second[0] > first[0] + position_tolerance_m
      and second[1] <= first[1] + position_tolerance_m
      and second[1] >= -axis_tolerance_m
      for first, second in zip(shock_points, shock_points[1:])
    )
  )
  upstream_total_residuals: list[float] = []
  pressure_samples_valid = len(upstream_pressures) == len(shock_points)
  if pressure_samples_valid:
    for state, pressure in zip(upstream_states, upstream_pressures, strict=True):
      if not isinstance(state, CharacteristicState) or not isfinite(float(pressure)) or pressure <= 0.0:
        pressure_samples_valid = False
        break
      upstream_total_residuals.append(
        _state_total_pressure(state, float(pressure))
      )
  patch_types_valid = all(
    isinstance(sample, MocPostShockBoundaryState)
    for sample in patch
  )
  patch_points_valid = bool(patch_types_valid and patch) and all(
    hypot(
      sample.point_m[0] - shock_points[index][0],
      sample.point_m[1] - shock_points[index][1],
    ) <= state_tolerance
    for index, sample in enumerate(patch)
  )
  patch_pressure_loss_verified = bool(
    patch_types_valid
    and pressure_samples_valid
    and patch_points_valid
    and all(
      sample.state.mach > 1.0
      and sample.upstream_total_pressure_Pa > 0.0
      and sample.downstream_total_pressure_Pa > 0.0
      and sample.downstream_total_pressure_Pa < sample.upstream_total_pressure_Pa
      and _relative_value_residual(
        sample.upstream_total_pressure_Pa,
        upstream_total_residuals[index],
      ) <= pressure_tolerance
      for index, sample in enumerate(patch)
    )
  )
  terminal_pressure_loss_verified = bool(
    patch_pressure_loss_verified
    and terminal_normal_shock_verified
    and terminal_ratio is not None
    and terminal_ratio < 1.0
  )
  supersonic_patch_verified = bool(
    patch_pressure_loss_verified
    and len(patch) == len(shock_points) - 1
  )
  ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in patch
    if isinstance(sample, MocPostShockBoundaryState)
    and sample.upstream_total_pressure_Pa > 0.0
  )
  if terminal_ratio is not None:
    ratios = (*ratios, terminal_ratio)
  minimum_ratio = min(ratios) if ratios else None
  maximum_ratio = max(ratios) if ratios else None
  mixed_regime_topology = _empty_topology()
  perimeter_sample_count = 0
  mixed_regime_node_count = 0
  mixed_regime_cell_count = 0
  mixed_regime_request_verified = False
  mixed_regime_boundary_verified = False
  mixed_regime_model_verified = False
  downstream_condition_verified = False
  maximum_thermodynamic_residual: float | None = None
  maximum_harmonic_residual: float | None = None
  maximum_velocity_divergence_residual: float | None = None
  mixed_regime_potential_model_verified: bool | None = None
  maximum_mass_conservation_residual: float | None = None
  maximum_boundary_normal_velocity_residual: float | None = None
  potential_circulation_residual: float | None = None
  mixed_messages: list[str] = []
  if closure is None:
    mixed_messages.append(
      'no mixed-regime closure was supplied; the terminal remains an open '
      'physical-closure boundary'
    )
  elif not isinstance(closure, MocMixedRegimeClosureResult):
    mixed_messages.append(
      'mixed_regime_closure must be a MocMixedRegimeClosureResult'
    )
  elif not terminal_normal_shock_verified or not isinstance(
    terminal,
    MocNormalShockTerminalResult,
  ):
    mixed_messages.append(
      'mixed-regime closure cannot be seam-checked without a verified normal shock'
    )
  else:
    try:
      expected_request = field.mixed_regime_perimeter_request()
      mixed_regime_request_verified = closure.request == expected_request
    except (TypeError, ValueError) as error:
      mixed_messages.append(f'mixed-regime terminal request could not be checked: {error}')
    if not mixed_regime_request_verified:
      mixed_messages.append(
        'mixed-regime closure request does not retain the exact terminal seam'
      )
    mixed_field = closure.field
    if not isinstance(mixed_field, MocMixedRegimeFieldResult):
      mixed_messages.append(
        'mixed-regime closure did not provide a MocMixedRegimeFieldResult'
      )
    else:
      mixed_regime_node_count = len(mixed_field.nodes)
      mixed_regime_cell_count = len(mixed_field.cells)
      perimeter_sample_count = len(mixed_field.boundary.perimeter_points_m)
      try:
        mixed_regime_topology = validate_moc_mesh(
          mixed_field.cells,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        mixed_messages.append(f'mixed-regime mesh could not be measured: {error}')
      try:
        mixed_cells_geometry_valid = bool(mixed_field.cells) and all(
          len(_cell_vertices(cell)) == 3
          for cell in mixed_field.cells
        )
      except (AttributeError, TypeError, ValueError):
        mixed_cells_geometry_valid = False
      samples_valid = all(
        isinstance(sample, MocMixedRegimeFieldSample)
        and all(isfinite(float(value)) for value in (
          *sample.point_m,
          sample.mach,
          sample.flow_angle_rad,
          sample.static_pressure_Pa,
          sample.total_pressure_Pa,
          sample.gamma,
        ))
        for sample in mixed_field.nodes
      )
      try:
        independent_boundary = validate_mixed_regime_boundary(
          terminal,
          patch,
          supersonic_patch_converged=True,
          subsonic_samples=mixed_field.boundary.subsonic_samples,
          perimeter_points_m=mixed_field.boundary.perimeter_points_m,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
          pressure_tolerance=pressure_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        independent_boundary = None
        mixed_messages.append(f'mixed-regime scalar seam could not be measured: {error}')
      if independent_boundary is not None:
        mixed_regime_boundary_verified = independent_boundary.converged
      if not mixed_regime_boundary_verified:
        mixed_messages.append(
          'mixed-regime scalar perimeter did not pass an independent seam check'
        )
      maximum_thermodynamic_residual = _mixed_field_thermodynamic_residual(
        mixed_field.nodes,
      )
      maximum_harmonic_residual = _mixed_field_harmonic_residual(
        mixed_field,
        position_tolerance_m=position_tolerance_m,
      )
      maximum_velocity_divergence_residual = (
        _mixed_field_velocity_divergence_residual(
          mixed_field,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
      )
      common_model_gates = bool(
        mixed_field.converged
        and samples_valid
        and mixed_regime_node_count > 0
        and mixed_regime_cell_count > 0
        and mixed_cells_geometry_valid
        and mixed_regime_topology.connected
        and mixed_regime_topology.forms_closed_zone
        and not mixed_regime_topology.nonmanifold_edge_count
        and maximum_thermodynamic_residual is not None
        and maximum_thermodynamic_residual <= thermodynamic_tolerance
      )
      if mixed_field.model == 'compressible-isentropic-potential-reference':
        try:
          potential_measurement = measure_mixed_regime_compressible_potential_field(
            mixed_field,
            position_tolerance_m=position_tolerance_m,
            thermodynamic_tolerance=thermodynamic_tolerance,
            potential_tolerance=potential_circulation_tolerance,
            residual_tolerance=potential_residual_tolerance,
            velocity_tolerance=potential_velocity_tolerance,
            mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
          potential_measurement = None
          mixed_messages.append(
            f'independent potential reference measurement failed: {error}'
          )
        if potential_measurement is not None:
          mixed_regime_potential_model_verified = (
            potential_measurement.reference_model_verified
          )
          maximum_mass_conservation_residual = (
            potential_measurement.maximum_mass_conservation_residual
          )
          maximum_boundary_normal_velocity_residual = (
            potential_measurement.maximum_boundary_normal_velocity_residual
          )
          potential_circulation_residual = (
            potential_measurement.potential_circulation_residual
          )
          mixed_regime_model_verified = bool(
            common_model_gates
            and potential_measurement.reference_model_verified
          )
      elif mixed_field.model == 'solver-owned-subsonic-free-boundary-reference':
        pressure_scale = max(
          1.0,
          max(
            (
              abs(sample.static_pressure_Pa)
              for sample in mixed_field.boundary.subsonic_samples
            ),
            default=1.0,
          ),
        )
        mixed_regime_model_verified = bool(
          common_model_gates
          and maximum_harmonic_residual is not None
          and maximum_harmonic_residual <= residual_tolerance
          and mixed_field.maximum_mass_conservation_residual is not None
          and mixed_field.maximum_mass_conservation_residual <= residual_tolerance
          and mixed_field.free_boundary_pressure_residual_Pa is not None
          and mixed_field.free_boundary_pressure_residual_Pa
          <= pressure_tolerance * pressure_scale
          and mixed_field.free_boundary_tangent_residual_rad is not None
          and mixed_field.free_boundary_tangent_residual_rad <= residual_tolerance
          and mixed_field.centerline_tangent_residual_rad is not None
          and mixed_field.centerline_tangent_residual_rad <= residual_tolerance
          and mixed_field.outlet_pressure_residual_Pa is not None
          and mixed_field.outlet_pressure_residual_Pa
          <= pressure_tolerance * pressure_scale
          and mixed_field.free_boundary_geometry_residual_m is not None
          and mixed_field.free_boundary_geometry_residual_m <= position_tolerance_m
        )
      else:
        mixed_regime_model_verified = bool(
          common_model_gates
          and maximum_harmonic_residual is not None
          and maximum_harmonic_residual <= residual_tolerance
          and maximum_velocity_divergence_residual is not None
          and maximum_velocity_divergence_residual <= residual_tolerance
        )
      if not mixed_regime_model_verified:
        mixed_messages.append(
          'mixed-regime reference mesh or independently recomputed residuals failed'
        )
      condition = mixed_field.downstream_condition
      if (
        independent_boundary is not None
        and isinstance(condition, MocMixedRegimeDownstreamConditionResult)
        and condition.boundary == mixed_field.boundary
        and condition.condition_kind is not None
      ):
        ambient_pressure = None
        if condition.condition_kind in (
          MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
          MocMixedRegimeDownstreamConditionKind.AMBIENT_PRESSURE_FREE_BOUNDARY,
        ):
          if (
            closure.perimeter_spec is not None
            and closure.perimeter_spec.condition_kind is condition.condition_kind
            and closure.perimeter_spec.ambient_pressure_Pa is not None
          ):
            ambient_pressure = closure.perimeter_spec.ambient_pressure_Pa
          else:
            mixed_messages.append(
              'independent pressure-condition verification requires the '
              'explicit perimeter ambient pressure'
            )
        if (
          condition.condition_kind is MocMixedRegimeDownstreamConditionKind.SLIP_WALL
          or ambient_pressure is not None
        ):
          independent_condition = validate_mixed_regime_downstream_condition(
            independent_boundary,
            condition.condition_kind,
            ambient_pressure_Pa=ambient_pressure,
            position_tolerance_m=position_tolerance_m,
            tangent_tolerance_rad=1.0e-8,
            pressure_tolerance=pressure_tolerance,
          )
          downstream_condition_verified = bool(
            condition.converged and independent_condition.converged
          )
      if not downstream_condition_verified:
        mixed_messages.append(
          'mixed-regime downstream condition did not pass an independent check'
        )
  physical_closure_verified = bool(
    field.converged
    and supersonic_topology.connected
    and supersonic_topology.forms_closed_zone
    and not supersonic_topology.nonmanifold_edge_count
    and supersonic_node_count > 0
    and supersonic_cell_count > 0
    and terminal_normal_shock_verified
    and terminal_shock_geometry_verified
    and terminal_pressure_loss_verified
    and supersonic_patch_verified
    and mixed_regime_request_verified
    and mixed_regime_boundary_verified
    and mixed_regime_model_verified
    and downstream_condition_verified
  )
  physical_termination_verified = bool(
    physical_closure_verified and terminal_normal_shock_verified
  )
  if not supersonic_topology.connected or not supersonic_topology.forms_closed_zone:
    status = MocTerminalClosureMeasurementStatus.TOPOLOGY_FAILURE
    message = f'terminal supersonic topology failed independent measurement: {supersonic_topology.message}'
  elif not terminal_shock_geometry_verified:
    status = MocTerminalClosureMeasurementStatus.GEOMETRY_FAILURE
    message = (
      'terminal shock geometry did not pass independent measurement'
      + (f': {edge_error}' if edge_error else '')
    )
  elif not terminal_pressure_loss_verified:
    status = MocTerminalClosureMeasurementStatus.PRESSURE_FAILURE
    message = 'terminal shock total-pressure loss did not pass independent measurement'
  elif not terminal_normal_shock_verified or not supersonic_patch_verified:
    status = MocTerminalClosureMeasurementStatus.SUPERSONIC_FAILURE
    message = 'terminal normal-shock or supersonic-patch checks failed independent measurement'
  elif not physical_closure_verified:
    status = MocTerminalClosureMeasurementStatus.MIXED_REGIME_FAILURE
    message = '; '.join(mixed_messages) or 'mixed-regime closure did not pass independent measurement'
  else:
    status = MocTerminalClosureMeasurementStatus.CONVERGED
    message = (
      'terminal supersonic region and supplied mixed-regime closure passed '
      'independent geometry, topology, seam, pressure, and residual checks; '
      'the result remains a terminal stop and is not a production validation claim'
    )
  return _terminal_measurement_failure(
    status,
    terminal_field_status=terminal_field_status,
    mixed_regime_status=mixed_regime_status,
    supersonic_topology=supersonic_topology,
    mixed_regime_topology=mixed_regime_topology,
    terminal_shock_sample_count=len(shock_points),
    terminal_shock_edge_count=terminal_shock_edge_count,
    terminal_shock_downstream_sample_count=len(patch),
    perimeter_sample_count=perimeter_sample_count,
    supersonic_node_count=supersonic_node_count,
    supersonic_cell_count=supersonic_cell_count,
    mixed_regime_node_count=mixed_regime_node_count,
    mixed_regime_cell_count=mixed_regime_cell_count,
    terminal_normal_shock_verified=terminal_normal_shock_verified,
    terminal_shock_geometry_verified=terminal_shock_geometry_verified,
    terminal_pressure_loss_verified=terminal_pressure_loss_verified,
    supersonic_patch_verified=supersonic_patch_verified,
    mixed_regime_request_verified=mixed_regime_request_verified,
    mixed_regime_boundary_verified=mixed_regime_boundary_verified,
    mixed_regime_model_verified=mixed_regime_model_verified,
    downstream_condition_verified=downstream_condition_verified,
    physical_closure_verified=physical_closure_verified,
    physical_termination_verified=physical_termination_verified,
    minimum_terminal_total_pressure_ratio=minimum_ratio,
    maximum_terminal_total_pressure_ratio=maximum_ratio,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    mixed_regime_potential_model_verified=mixed_regime_potential_model_verified,
    maximum_mass_conservation_residual=maximum_mass_conservation_residual,
    maximum_boundary_normal_velocity_residual=(
      maximum_boundary_normal_velocity_residual
    ),
    potential_circulation_residual=potential_circulation_residual,
    message=message,
  )
####


def _caustic_remesh_measurement_failure(
  status: MocCausticRemeshMeasurementStatus,
  *,
  remesh_status: str | None = None,
  bridge_status: str | None = None,
  event_point_m: Point | None = None,
  shock_sample_count: int = 0,
  shock_fit_sample_count: int = 0,
  field_node_count: int = 0,
  field_cell_count: int = 0,
  incoming_handoff_sample_count: int = 0,
  incoming_handoff_verified: bool | None = None,
  field_topology: MocTopologyResult | None = None,
  first_missing_sample_index: int | None = None,
  first_missing_point_m: Point | None = None,
  event_point_verified: bool = False,
  event_state_verified: bool = False,
  event_pressure_verified: bool = False,
  local_bridge_verified: bool = False,
  shock_geometry_verified: bool = False,
  shock_fit_verified: bool = False,
  shock_pressure_loss_verified: bool = False,
  upstream_field_verified: bool = False,
  upstream_bridge_verified: bool | None = None,
  field_topology_verified: bool = False,
  field_boundary_verified: bool = False,
  field_state_carry_verified: bool = False,
  field_residuals_verified: bool = False,
  downstream_field_verified: bool = False,
  remesh_seam_verified: bool = False,
  bounded_remesh_verified: bool = False,
  maximum_shock_angle_residual_rad: float | None = None,
  maximum_field_geometry_residual_m: float | None = None,
  maximum_field_invariant_residual: float | None = None,
  minimum_total_pressure_ratio: float | None = None,
  maximum_total_pressure_ratio: float | None = None,
  message: str,
) -> MocCausticRemeshMeasurement:
  return MocCausticRemeshMeasurement(
    status=status,
    operator_id=MOC_CAUSTIC_REMESH_OPERATOR_ID,
    remesh_status=remesh_status,
    bridge_status=bridge_status,
    event_point_m=event_point_m,
    shock_sample_count=shock_sample_count,
    shock_fit_sample_count=shock_fit_sample_count,
    field_node_count=field_node_count,
    field_cell_count=field_cell_count,
    incoming_handoff_sample_count=incoming_handoff_sample_count,
    incoming_handoff_verified=incoming_handoff_verified,
    field_topology=_empty_topology() if field_topology is None else field_topology,
    first_missing_sample_index=first_missing_sample_index,
    first_missing_point_m=first_missing_point_m,
    event_point_verified=event_point_verified,
    event_state_verified=event_state_verified,
    event_pressure_verified=event_pressure_verified,
    local_bridge_verified=local_bridge_verified,
    shock_geometry_verified=shock_geometry_verified,
    shock_fit_verified=shock_fit_verified,
    shock_pressure_loss_verified=shock_pressure_loss_verified,
    upstream_field_verified=upstream_field_verified,
    upstream_bridge_verified=upstream_bridge_verified,
    field_topology_verified=field_topology_verified,
    field_boundary_verified=field_boundary_verified,
    field_state_carry_verified=field_state_carry_verified,
    field_residuals_verified=field_residuals_verified,
    downstream_field_verified=downstream_field_verified,
    remesh_seam_verified=remesh_seam_verified,
    bounded_remesh_verified=bounded_remesh_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    maximum_shock_angle_residual_rad=maximum_shock_angle_residual_rad,
    maximum_field_geometry_residual_m=maximum_field_geometry_residual_m,
    maximum_field_invariant_residual=maximum_field_invariant_residual,
    minimum_total_pressure_ratio=minimum_total_pressure_ratio,
    maximum_total_pressure_ratio=maximum_total_pressure_ratio,
    claim_status='not_accepted',
    message=message,
  )
####


def _caustic_state_matches(
  actual: object,
  expected: object,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  if not isinstance(actual, CharacteristicState) or not isinstance(
    expected,
    CharacteristicState,
  ):
    return False
  return (
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad)
    <= state_tolerance * max(1.0, abs(actual.theta_rad), abs(expected.theta_rad))
    and abs(actual.mach - expected.mach)
    <= state_tolerance * max(1.0, abs(actual.mach), abs(expected.mach))
    and abs(actual.gamma - expected.gamma)
    <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
  )
####


def _caustic_points_match(
  actual: Sequence[Point],
  expected: Sequence[Point],
  *,
  position_tolerance_m: float,
) -> bool:
  return len(actual) == len(expected) and all(
    hypot(first[0] - second[0], first[1] - second[1])
    <= position_tolerance_m
    for first, second in zip(actual, expected, strict=True)
  )
####


def _pressure_matches(
  actual: object,
  expected: object,
  *,
  pressure_tolerance: float,
) -> bool:
  if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
    return False
  actual_value = float(actual)
  expected_value = float(expected)
  return (
    isfinite(actual_value)
    and isfinite(expected_value)
    and abs(actual_value - expected_value)
    <= pressure_tolerance * max(1.0, abs(actual_value), abs(expected_value))
  )
####


def _static_pressure_from_total_pressure_for_measurement(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  return float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
####


def measure_moc_caustic_remesh(
  observation: MocCausticRemeshObservation,
  *,
  target_centerline_y_m: float = 0.0,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  axis_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  residual_tolerance: float = 1.0e-10,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocCausticRemeshMeasurement:
  """Independently audit a bounded caustic shock/new-family remesh.

  The operator refits the attached shock from carried upstream samples,
  rebuilds the shock pressure-loss ratios, and rechecks the returned
  post-shock mesh and characteristic residuals.  An optional bridge is
  resampled along the complete retained path; a failed solver sample is
  included in that path so a bounded-domain gap cannot be hidden by a partial
  result.  A passing result is still a research remesh measurement, not a
  physically closed first cell.
  """

  if not isinstance(observation, MocCausticRemeshObservation):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      message='observation must be a MocCausticRemeshObservation',
    )
  for name, value in (
    ('target_centerline_y_m', target_centerline_y_m),
    ('position_tolerance_m', position_tolerance_m),
    ('axis_tolerance_m', axis_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('residual_tolerance', residual_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if name == 'target_centerline_y_m':
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    elif not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not isinstance(branch, ShockBranch):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      message='branch must be a ShockBranch',
    )

  remesh = observation.remesh_result
  if not isinstance(remesh, MocCausticShockRemeshResult):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      message='remesh_result must be a MocCausticShockRemeshResult',
    )
  remesh_status = getattr(remesh.status, 'value', str(remesh.status))
  bridge = observation.upstream_bridge
  if bridge is not None and not isinstance(bridge, MocCausticUpstreamBridge):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      message='upstream_bridge must be a MocCausticUpstreamBridge when supplied',
    )
  expected_handoff: tuple[MocChainBoundarySample, ...] | None = None
  incoming_handoff_verified: bool | None = None
  raw_handoff = observation.incoming_handoff
  if raw_handoff is not None:
    try:
      expected_handoff = tuple(raw_handoff)
    except TypeError:
      return _caustic_remesh_measurement_failure(
        MocCausticRemeshMeasurementStatus.INVALID_INPUT,
        remesh_status=remesh_status,
        message='incoming_handoff must be an iterable of MocChainBoundarySample values',
      )
    if len(expected_handoff) < 3 or any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in expected_handoff
    ):
      return _caustic_remesh_measurement_failure(
        MocCausticRemeshMeasurementStatus.INVALID_INPUT,
        remesh_status=remesh_status,
        incoming_handoff_sample_count=len(expected_handoff),
        incoming_handoff_verified=False,
        message=(
          'incoming_handoff must contain at least three '
          'MocChainBoundarySample values'
        ),
      )
    incoming_handoff_verified = False
  request = remesh.request
  if not isinstance(request, MocCausticShockRemeshRequest):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      message='caustic remesh result does not carry a request',
    )
  event_point: Point | None = None
  try:
    raw_event_point = request.event_point_m
    if len(raw_event_point) != 2 or not all(
      isfinite(float(value)) for value in raw_event_point
    ):
      raise ValueError('event point must contain two finite coordinates')
    event_point = (float(raw_event_point[0]), float(raw_event_point[1]))
  except (AttributeError, TypeError, ValueError) as error:
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      message=f'caustic remesh request event point could not be read: {error}',
    )

  event_point_verified = bool(
    remesh.event_point_m is not None
    and hypot(
      remesh.event_point_m[0] - event_point[0],
      remesh.event_point_m[1] - event_point[1],
    ) <= position_tolerance_m
  )
  shock = remesh.shock
  if not isinstance(shock, MocFreeBoundaryShockResult):
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.SHOCK_FAILURE,
      remesh_status=remesh_status,
      event_point_m=event_point,
      event_point_verified=event_point_verified,
      message='caustic remesh result does not carry a free-boundary shock result',
    )
  shock_sample_count = len(shock.shock_points_m)
  try:
    shock_points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock.shock_points_m
    )
    if not shock_points:
      raise ValueError('caustic shock boundary requires at least one point')
    if any(
      not all(isfinite(coordinate) for coordinate in point)
      for point in shock_points
    ):
      raise ValueError('caustic shock boundary points must be finite')
  except ValueError as error:
    return _caustic_remesh_measurement_failure(
      MocCausticRemeshMeasurementStatus.SHOCK_FAILURE,
      remesh_status=remesh_status,
      event_point_m=event_point,
      shock_sample_count=shock_sample_count,
      event_point_verified=event_point_verified,
      message=str(error),
    )

  arrays_aligned = len(shock_points) == len(shock.upstream_states) == len(
    shock.upstream_pressure_Pa
  ) == len(shock.downstream_flow_angles_rad) == len(
    shock.shock_angle_residuals_rad
  )
  state_coordinates_verified = bool(
    arrays_aligned
    and all(
      isinstance(state, CharacteristicState)
      and hypot(state.x_m - point[0], state.y_m - point[1])
      <= position_tolerance_m
      for state, point in zip(shock.upstream_states, shock_points, strict=True)
    )
  )
  pressure_samples_verified = bool(
    arrays_aligned
    and all(
      isfinite(float(pressure)) and float(pressure) > 0.0
      for pressure in shock.upstream_pressure_Pa
    )
  )
  event_state_verified = bool(
    arrays_aligned
    and _caustic_state_matches(
      shock.upstream_states[0],
      request.upstream_state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
    )
  )
  event_pressure_verified = bool(
    arrays_aligned
    and _pressure_matches(
      shock.upstream_pressure_Pa[0],
      request.upstream_static_pressure_Pa,
      pressure_tolerance=pressure_tolerance,
    )
  )
  shock_geometry_verified = bool(
    event_point_verified
    and hypot(
      shock_points[0][0] - event_point[0],
      shock_points[0][1] - event_point[1],
    ) <= position_tolerance_m
    and abs(shock_points[-1][1] - target_centerline_y_m) <= axis_tolerance_m
    and all(
      point[1] >= -axis_tolerance_m
      for point in shock_points
    )
    and all(
      second[0] > first[0] + position_tolerance_m
      and second[1] <= first[1] + position_tolerance_m
      for first, second in zip(shock_points, shock_points[1:])
    )
  )
  upstream_field_verified = bool(
    arrays_aligned
    and state_coordinates_verified
    and pressure_samples_verified
    and all(isfinite(float(value)) for value in shock.downstream_flow_angles_rad)
    and all(isfinite(float(value)) for value in shock.shock_angle_residuals_rad)
  )

  bridge_status: str | None = None
  upstream_bridge_verified: bool | None = None
  first_missing_sample_index: int | None = None
  first_missing_point_m: Point | None = None
  if bridge is not None:
    bridge_path = list(shock_points)
    if shock.failed_point_m is not None and (
      not bridge_path
      or hypot(
        shock.failed_point_m[0] - bridge_path[-1][0],
        shock.failed_point_m[1] - bridge_path[-1][1],
      ) > position_tolerance_m
    ):
      bridge_path.append(shock.failed_point_m)
    try:
      bridge_audit = sample_caustic_upstream_bridge(
        bridge,
        bridge_path,
        position_tolerance_m=position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      bridge_audit = None
      bridge_status = 'measurement_exception'
      bridge_message = f'caustic bridge measurement raised: {error}'
    else:
      bridge_status = bridge_audit.status.value
      first_missing_sample_index = bridge_audit.first_missing_sample_index
      first_missing_point_m = bridge_audit.first_missing_point_m
      bridge_samples_match = len(bridge_audit.samples) >= len(shock_points) and all(
        _caustic_state_matches(
          sample.state,
          shock.upstream_states[index],
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        )
        and _pressure_matches(
          sample.static_pressure_Pa,
          shock.upstream_pressure_Pa[index],
          pressure_tolerance=pressure_tolerance,
        )
        for index, sample in enumerate(bridge_audit.samples[:len(shock_points)])
      )
      upstream_bridge_verified = bool(
        bridge_audit.converged and bridge_samples_match
      )
      bridge_message = (
        'caustic upstream bridge did not cover the complete retained shock path'
        if not upstream_bridge_verified
        else ''
      )
    if not upstream_bridge_verified:
      return _caustic_remesh_measurement_failure(
        MocCausticRemeshMeasurementStatus.UPSTREAM_FAILURE,
        remesh_status=remesh_status,
        bridge_status=bridge_status,
        event_point_m=event_point,
        shock_sample_count=shock_sample_count,
        incoming_handoff_sample_count=(
          len(expected_handoff)
          if expected_handoff is not None
          else (
            0
            if shock.field is None
            else len(shock.field.incoming_handoff_states)
          )
        ),
        incoming_handoff_verified=incoming_handoff_verified,
        first_missing_sample_index=first_missing_sample_index,
        first_missing_point_m=first_missing_point_m,
        event_point_verified=event_point_verified,
        event_state_verified=event_state_verified,
        event_pressure_verified=event_pressure_verified,
        shock_geometry_verified=shock_geometry_verified,
        upstream_field_verified=upstream_field_verified,
        upstream_bridge_verified=False,
        message=bridge_message,
      )

  refit: MocShockBoundaryFitResult | None = None
  refit_message = ''
  if shock_geometry_verified and upstream_field_verified:
    try:
      refit = fit_attached_shock_boundary(
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        shock_points,
        shock.downstream_flow_angles_rad,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      refit_message = f'independent attached-shock refit raised: {error}'
  if refit is not None:
    refit_message = refit.message
  shock_fit_sample_count = 0 if refit is None else len(refit.boundary_states)
  reported_fit = shock.shock_fit
  reported_fit_consistent = bool(
    isinstance(reported_fit, MocShockBoundaryFitResult)
    and reported_fit.converged
    and refit is not None
    and refit.converged
    and len(reported_fit.boundary_states) == len(refit.boundary_states)
    and len(reported_fit.upstream_states) == len(shock.upstream_states)
    and len(reported_fit.upstream_total_pressure_Pa) == len(shock_points)
    and all(
      _caustic_state_matches(
        actual.state,
        expected.state,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
      )
      and _pressure_matches(
        actual.upstream_total_pressure_Pa,
        expected.upstream_total_pressure_Pa,
        pressure_tolerance=pressure_tolerance,
      )
      and _pressure_matches(
        actual.downstream_total_pressure_Pa,
        expected.downstream_total_pressure_Pa,
        pressure_tolerance=pressure_tolerance,
      )
      for actual, expected in zip(
        reported_fit.boundary_states,
        refit.boundary_states,
        strict=True,
      )
    )
  )
  shock_fit_verified = bool(
    refit is not None
    and refit.converged
    and refit.maximum_shock_angle_residual_rad is not None
    and reported_fit_consistent
  )
  ratios: tuple[float, ...] = ()
  if refit is not None and refit.converged:
    ratio_values: list[float] = []
    pressure_consistent = True
    try:
      for state, pressure, boundary in zip(
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        refit.boundary_states,
        strict=True,
      ):
        expected_upstream_total = _state_total_pressure(state, pressure)
        pressure_consistent = pressure_consistent and (
          _pressure_matches(
            expected_upstream_total,
            boundary.upstream_total_pressure_Pa,
            pressure_tolerance=pressure_tolerance,
          )
          and boundary.downstream_total_pressure_Pa > 0.0
          and boundary.downstream_total_pressure_Pa
          < boundary.upstream_total_pressure_Pa
        )
        ratio_values.append(
          boundary.downstream_total_pressure_Pa
          / boundary.upstream_total_pressure_Pa
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError, ZeroDivisionError):
      pressure_consistent = False
      ratio_values = []
    ratios = tuple(ratio_values)
    shock_pressure_loss_verified = bool(
      shock_fit_verified
      and pressure_consistent
      and ratios
      and all(isfinite(value) and 0.0 < value < 1.0 for value in ratios)
    )
  else:
    shock_pressure_loss_verified = False
  maximum_shock_angle_residual_rad = (
    None
    if refit is None
    else refit.maximum_shock_angle_residual_rad
  )
  minimum_total_pressure_ratio = min(ratios) if ratios else None
  maximum_total_pressure_ratio = max(ratios) if ratios else None

  local_bridge_verified = False
  if shock_fit_verified and refit is not None and refit.boundary_states:
    bridge_state = getattr(request.local_bridge, 'downstream_state', None)
    compression = getattr(request.local_bridge, 'compression', None)
    compression_pressure = (
      None if compression is None
      else getattr(compression, 'downstream_total_pressure_Pa', None)
    )
    local_bridge_verified = bool(
      _caustic_state_matches(
        refit.boundary_states[0].state,
        bridge_state,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
      )
      and compression_pressure is not None
      and _pressure_matches(
        refit.boundary_states[0].downstream_total_pressure_Pa,
        compression_pressure,
        pressure_tolerance=pressure_tolerance,
      )
    )

  field = shock.field
  field_topology = _empty_topology()
  field_node_count = 0
  field_cell_count = 0
  incoming_handoff_sample_count = 0
  if expected_handoff is not None:
    incoming_handoff_sample_count = len(expected_handoff)
  field_boundary_verified = False
  field_state_carry_verified = False
  field_residuals_verified = False
  maximum_field_geometry_residual_m: float | None = None
  maximum_field_invariant_residual: float | None = None
  field_topology_verified = False
  if isinstance(field, MocPostShockCharacteristicFieldResult):
    field_node_count = len(field.nodes)
    field_cell_count = len(field.cells)
    if expected_handoff is None:
      incoming_handoff_sample_count = len(field.incoming_handoff_states)
    try:
      field_topology = validate_moc_mesh(
        field.cells,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
      field_topology_verified = bool(
        field_topology.connected
        and field_topology.forms_closed_zone
        and not field_topology.nonmanifold_edge_count
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      field_topology = _empty_topology()
      field_topology_verified = False
    try:
      field_shock_points = _points(
        field.shock_boundary_points_m,
        'caustic remesh field shock boundary',
      )
      field_centerline_points = _points(
        field.centerline_boundary_points_m,
        'caustic remesh field centerline boundary',
      )
      field_edges, field_vertices = _edge_counts(
        field.cells,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
      field_perimeter = _perimeter_points(field_edges, field_vertices)
      field_boundary_verified = bool(
        field.status is MocPostShockFieldStatus.CONVERGED_CLOSED
        and _caustic_points_match(
          field_shock_points,
          shock_points,
          position_tolerance_m=position_tolerance_m,
        )
        and _validate_polyline(
          field_shock_points,
          'caustic remesh field shock boundary',
          position_tolerance_m=position_tolerance_m,
          require_strict_x=True,
        ) is None
        and _validate_polyline(
          field_centerline_points,
          'caustic remesh field centerline boundary',
          position_tolerance_m=position_tolerance_m,
          require_strict_x=False,
        ) is None
        and hypot(
          field_centerline_points[0][0] - shock_points[-1][0],
          field_centerline_points[0][1] - shock_points[-1][1],
        ) <= position_tolerance_m
        and abs(field_centerline_points[-1][1] - target_centerline_y_m)
        <= axis_tolerance_m
        and _polyline_has_boundary_edges(
          field_shock_points,
          field_edges,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
        and _polyline_has_boundary_edges(
          field_centerline_points,
          field_edges,
          vertex_tolerance_m=mesh_vertex_tolerance_m,
        )
        and field_perimeter is not None
      )
    except (AttributeError, TypeError, ValueError):
      field_boundary_verified = False

    if refit is not None and refit.converged:
      incoming_handoff_matches = (
        expected_handoff is None
        or (
          len(field.incoming_handoff_states) == len(expected_handoff)
          and len(field.incoming_handoff_total_pressure_Pa) == len(expected_handoff)
          and all(
            _caustic_state_matches(
              actual,
              expected.state,
              position_tolerance_m=position_tolerance_m,
              state_tolerance=state_tolerance,
            )
            and _pressure_matches(
              pressure,
              expected.total_pressure_Pa,
              pressure_tolerance=pressure_tolerance,
            )
            for actual, pressure, expected in zip(
              field.incoming_handoff_states,
              field.incoming_handoff_total_pressure_Pa,
              expected_handoff,
              strict=True,
            )
          )
        )
      )
      if expected_handoff is not None:
        incoming_handoff_verified = bool(incoming_handoff_matches)
      field_state_carry_verified = bool(
        len(field.shock_boundary_states) == len(refit.boundary_states)
        and len(field.shock_boundary_total_pressure_Pa) == len(refit.boundary_states)
        and all(
          _caustic_state_matches(
            actual,
            expected.state,
            position_tolerance_m=position_tolerance_m,
            state_tolerance=state_tolerance,
          )
          and _pressure_matches(
            pressure,
            expected.downstream_total_pressure_Pa,
            pressure_tolerance=pressure_tolerance,
          )
          for actual, pressure, expected in zip(
            field.shock_boundary_states,
            field.shock_boundary_total_pressure_Pa,
            refit.boundary_states,
            strict=True,
          )
        )
        and len(field.upstream_boundary_states) == len(shock.upstream_states)
        and len(field.upstream_boundary_total_pressure_Pa) == len(shock_points)
        and all(
          _caustic_state_matches(
            actual,
            expected,
            position_tolerance_m=position_tolerance_m,
            state_tolerance=state_tolerance,
          )
          and _pressure_matches(
            pressure,
            boundary.upstream_total_pressure_Pa,
            pressure_tolerance=pressure_tolerance,
          )
          for actual, pressure, expected, boundary in zip(
            field.upstream_boundary_states,
            field.upstream_boundary_total_pressure_Pa,
            shock.upstream_states,
            refit.boundary_states,
            strict=True,
          )
        )
        and len(field.incoming_handoff_states) == len(
          field.incoming_handoff_total_pressure_Pa
        )
        and len(field.incoming_handoff_states) >= 3
        and all(isinstance(state, CharacteristicState) for state in field.incoming_handoff_states)
        and all(
          isfinite(float(pressure)) and float(pressure) > 0.0
          for pressure in field.incoming_handoff_total_pressure_Pa
        )
        and incoming_handoff_matches
        and len(field.continuation_boundary_states) == len(
          field.continuation_boundary_total_pressure_Pa
        )
        and len(field.continuation_boundary_states) >= 2
        and all(
          isinstance(state, CharacteristicState)
          for state in field.continuation_boundary_states
        )
        and all(
          isfinite(float(pressure)) and float(pressure) > 0.0
          for pressure in field.continuation_boundary_total_pressure_Pa
        )
      )

    geometry_residuals: list[float] = []
    invariant_residuals: list[float] = []
    node_data_verified = bool(field.nodes and field.cells)
    for node in field.nodes:
      point_result = getattr(node, 'point_result', None)
      point = getattr(node, 'point_m', None)
      state = getattr(node, 'state', None)
      pressure = getattr(node, 'total_pressure_Pa', None)
      geometry_residual = getattr(point_result, 'geometry_residual', None)
      invariant_values = (
        getattr(point_result, 'invariant_residual_plus', None),
        getattr(point_result, 'invariant_residual_minus', None),
      )
      pressure_value = (
        float(pressure)
        if isinstance(pressure, (int, float))
        else None
      )
      node_data_verified = node_data_verified and bool(
        isinstance(node, MocCharacteristicNode)
        and isinstance(state, CharacteristicState)
        and point is not None
        and len(point) == 2
        and all(isfinite(float(value)) for value in point)
        and hypot(state.x_m - float(point[0]), state.y_m - float(point[1]))
        <= position_tolerance_m
        and pressure_value is not None
        and isfinite(pressure_value)
        and pressure_value > 0.0
        and getattr(point_result, 'converged', False)
        and geometry_residual is not None
        and isfinite(float(geometry_residual))
        and abs(float(geometry_residual)) <= residual_tolerance
        and all(
          value is None or (
            isfinite(float(value)) and abs(float(value)) <= residual_tolerance
          )
          for value in invariant_values
        )
      )
      if geometry_residual is not None and isfinite(float(geometry_residual)):
        geometry_residuals.append(abs(float(geometry_residual)))
      invariant_residuals.extend(
        abs(float(value))
        for value in invariant_values
        if value is not None and isfinite(float(value))
      )
    maximum_field_geometry_residual_m = max(geometry_residuals, default=None)
    maximum_field_invariant_residual = max(invariant_residuals, default=None)
    reported_geometry_residual = field.maximum_geometry_residual_m
    reported_invariant_residual = field.maximum_absolute_invariant_residual
    reported_residuals_verified = bool(
      maximum_field_geometry_residual_m is not None
      and maximum_field_invariant_residual is not None
      and reported_geometry_residual is not None
      and reported_invariant_residual is not None
      and isfinite(float(reported_geometry_residual))
      and isfinite(float(reported_invariant_residual))
      and _relative_value_residual(
        float(reported_geometry_residual),
        maximum_field_geometry_residual_m,
      ) <= residual_tolerance
      and _relative_value_residual(
        float(reported_invariant_residual),
        maximum_field_invariant_residual,
      ) <= residual_tolerance
    )
    field_residuals_verified = bool(
      node_data_verified and reported_residuals_verified
    )

  downstream_field_verified = bool(
    isinstance(field, MocPostShockCharacteristicFieldResult)
    and field_topology_verified
    and field_boundary_verified
    and field_state_carry_verified
    and field_residuals_verified
  )
  remesh_seam_verified = bool(
    event_point_verified
    and event_state_verified
    and event_pressure_verified
    and shock_geometry_verified
    and shock_fit_verified
    and shock_pressure_loss_verified
    and local_bridge_verified
  )
  bounded_remesh_verified = bool(
    remesh_seam_verified
    and upstream_field_verified
    and downstream_field_verified
    and (bridge is None or upstream_bridge_verified)
  )
  if not event_point_verified or not event_state_verified or not event_pressure_verified:
    status = MocCausticRemeshMeasurementStatus.EVENT_FAILURE
    message = 'caustic remesh event point, state, or pressure seam failed independent measurement'
  elif not upstream_field_verified:
    status = MocCausticRemeshMeasurementStatus.UPSTREAM_FAILURE
    message = 'caustic remesh did not carry an aligned finite upstream shock field'
  elif not shock_geometry_verified or not shock_fit_verified or not shock_pressure_loss_verified:
    status = MocCausticRemeshMeasurementStatus.SHOCK_FAILURE
    message = refit_message or 'caustic remesh shock curve failed independent measurement'
  elif not local_bridge_verified or not remesh_seam_verified:
    status = MocCausticRemeshMeasurementStatus.SEAM_FAILURE
    message = 'caustic remesh local bridge seam failed independent measurement'
  elif not downstream_field_verified:
    status = MocCausticRemeshMeasurementStatus.FIELD_FAILURE
    message = 'caustic remesh downstream characteristic field failed independent measurement'
  else:
    status = MocCausticRemeshMeasurementStatus.CONVERGED
    message = (
      'bounded caustic remesh passed independent event, shock, pressure, '
      'topology, state-carry, and characteristic-residual checks; physical '
      'old/new-family and ambient closure remain separate pending gates'
    )
  return _caustic_remesh_measurement_failure(
    status,
    remesh_status=remesh_status,
    bridge_status=bridge_status,
    event_point_m=event_point,
    shock_sample_count=shock_sample_count,
    shock_fit_sample_count=shock_fit_sample_count,
    field_node_count=field_node_count,
    field_cell_count=field_cell_count,
    incoming_handoff_sample_count=incoming_handoff_sample_count,
    incoming_handoff_verified=incoming_handoff_verified,
    field_topology=field_topology,
    first_missing_sample_index=first_missing_sample_index,
    first_missing_point_m=first_missing_point_m,
    event_point_verified=event_point_verified,
    event_state_verified=event_state_verified,
    event_pressure_verified=event_pressure_verified,
    local_bridge_verified=local_bridge_verified,
    shock_geometry_verified=shock_geometry_verified,
    shock_fit_verified=shock_fit_verified,
    shock_pressure_loss_verified=shock_pressure_loss_verified,
    upstream_field_verified=upstream_field_verified,
    upstream_bridge_verified=upstream_bridge_verified,
    field_topology_verified=field_topology_verified,
    field_boundary_verified=field_boundary_verified,
    field_state_carry_verified=field_state_carry_verified,
    field_residuals_verified=field_residuals_verified,
    downstream_field_verified=downstream_field_verified,
    remesh_seam_verified=remesh_seam_verified,
    bounded_remesh_verified=bounded_remesh_verified,
    maximum_shock_angle_residual_rad=maximum_shock_angle_residual_rad,
    maximum_field_geometry_residual_m=maximum_field_geometry_residual_m,
    maximum_field_invariant_residual=maximum_field_invariant_residual,
    minimum_total_pressure_ratio=minimum_total_pressure_ratio,
    maximum_total_pressure_ratio=maximum_total_pressure_ratio,
    message=message,
  )
####


def _reflected_domain_remesh_measurement_failure(
  status: MocReflectedDomainRemeshMeasurementStatus,
  *,
  remesh_status: str | None = None,
  incoming_trace_polarity: str | None = None,
  incoming_trace_sample_count: int = 0,
  centerline_source_count: int = 0,
  outer_source_count: int = 0,
  source_node_count: int = 0,
  source_cell_count: int = 0,
  source_topology: MocTopologyResult | None = None,
  result_status_verified: bool = False,
  incoming_trace_verified: bool = False,
  polarity_verified: bool = False,
  reflection_seam_verified: bool = False,
  centerline_source_verified: bool = False,
  outer_source_verified: bool = False,
  total_pressure_verified: bool = False,
  source_topology_verified: bool = False,
  source_sampling_verified: bool = False,
  bounded_remesh_verified: bool = False,
  message: str,
) -> MocReflectedDomainRemeshMeasurement:
  return MocReflectedDomainRemeshMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_REMESH_OPERATOR_ID,
    remesh_status=remesh_status,
    incoming_trace_polarity=incoming_trace_polarity,
    incoming_trace_sample_count=incoming_trace_sample_count,
    centerline_source_count=centerline_source_count,
    outer_source_count=outer_source_count,
    source_node_count=source_node_count,
    source_cell_count=source_cell_count,
    source_topology=(
      _empty_topology() if source_topology is None else source_topology
    ),
    result_status_verified=result_status_verified,
    incoming_trace_verified=incoming_trace_verified,
    polarity_verified=polarity_verified,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    total_pressure_verified=total_pressure_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_remesh_verified=bounded_remesh_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status='independent-reflected-domain-remesh-audit; not-accepted',
    message=message,
  )
####


def measure_moc_reflected_domain_remesh(
  remesh: MocReflectedDomainRemeshResult,
) -> MocReflectedDomainRemeshMeasurement:
  """Independently audit one bounded reflected-domain source remesh.

  The operator remeasures the raw request and source-strip data.  In
  particular, it does not use ``reflection_seam_verified``,
  ``centerline_source_verified``, ``outer_source_verified``, or
  ``source_field_verified`` from the solver result as acceptance evidence.
  Passing therefore means only that the explicit Cauchy remesh is locally
  bounded and reproducible; canonical free-boundary closure and chain
  promotion remain separate gates.
  """

  if not isinstance(remesh, MocReflectedDomainRemeshResult):
    return _reflected_domain_remesh_measurement_failure(
      MocReflectedDomainRemeshMeasurementStatus.INVALID_INPUT,
      message=(
        'remesh must be a MocReflectedDomainRemeshResult'
      ),
    )

  remesh_status = getattr(remesh.status, 'value', str(remesh.status))
  result_status_verified = (
    remesh.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  )
  request = remesh.request
  if request is None:
    return _reflected_domain_remesh_measurement_failure(
      MocReflectedDomainRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      result_status_verified=result_status_verified,
      message='reflected-domain remesh result does not carry a request',
    )

  incoming = tuple(request.incoming_trace)
  centerline = tuple(request.centerline_source_states)
  outer = tuple(request.outer_source_states)
  incoming_count = len(incoming)
  centerline_count = len(centerline)
  outer_count = len(outer)

  try:
    incoming_validation = validate_characteristic_trace(
      incoming,
      CharacteristicFamily.MINUS,
      position_tolerance_m=request.position_tolerance_m,
      forward_position_tolerance_m=request.trace_forward_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _reflected_domain_remesh_measurement_failure(
      MocReflectedDomainRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      incoming_trace_sample_count=incoming_count,
      centerline_source_count=centerline_count,
      outer_source_count=outer_count,
      result_status_verified=result_status_verified,
      message=f'incoming reflected trace measurement raised: {error}',
    )
  incoming_trace_verified = incoming_validation.converged

  try:
    polarity = classify_reflected_trace_polarity(
      incoming,
      target_centerline_y_m=request.target_centerline_y_m,
      target_centerline_flow_angle_rad=request.target_centerline_flow_angle_rad,
      position_tolerance_m=request.position_tolerance_m,
      forward_position_tolerance_m=request.trace_forward_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _reflected_domain_remesh_measurement_failure(
      MocReflectedDomainRemeshMeasurementStatus.INVALID_INPUT,
      remesh_status=remesh_status,
      incoming_trace_sample_count=incoming_count,
      centerline_source_count=centerline_count,
      outer_source_count=outer_count,
      result_status_verified=result_status_verified,
      incoming_trace_verified=incoming_trace_verified,
      message=f'reflected trace polarity measurement raised: {error}',
    )
  incoming_trace_polarity = getattr(polarity.status, 'value', str(polarity.status))
  polarity_verified = bool(
    polarity.converged
    and (
      request.declared_polarity is None
      or request.declared_polarity is polarity.status
    )
  )

  reflection_seam_verified = False
  if incoming and centerline:
    anchor = incoming[-1]
    first_centerline = centerline[0]
    reflection_seam_verified = bool(
      abs(anchor.state.y_m - request.target_centerline_y_m)
      <= request.position_tolerance_m
      and abs(anchor.state.theta_rad - request.target_centerline_flow_angle_rad)
      <= request.invariant_tolerance
      and _caustic_state_matches(
        first_centerline,
        anchor.state,
        position_tolerance_m=request.position_tolerance_m,
        state_tolerance=request.invariant_tolerance,
      )
      and _pressure_matches(
        anchor.total_pressure_Pa,
        request.total_pressure_Pa,
        pressure_tolerance=request.pressure_tolerance,
      )
    )

  centerline_source_verified = bool(
    len(centerline) >= 3
    and all(isinstance(state, CharacteristicState) for state in centerline)
    and len(request.centerline_total_pressure_Pa) == len(centerline)
    and all(
      isfinite(float(pressure)) and float(pressure) > 0.0
      for pressure in request.centerline_total_pressure_Pa
    )
    and all(
      abs(state.gamma - centerline[0].gamma) <= request.invariant_tolerance
      and abs(state.y_m - request.target_centerline_y_m)
      <= request.position_tolerance_m
      and abs(state.theta_rad - request.target_centerline_flow_angle_rad)
      <= request.invariant_tolerance
      for state in centerline
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(centerline, centerline[1:])
    )
  )
  centerline_reference_state = centerline[0] if centerline else None
  outer_source_verified = bool(
    len(outer) >= 3
    and len(outer) == len(centerline)
    and centerline_reference_state is not None
    and all(isinstance(state, CharacteristicState) for state in outer)
    and all(
      abs(state.gamma - centerline_reference_state.gamma)
      <= request.invariant_tolerance
      and state.y_m > request.target_centerline_y_m + request.position_tolerance_m
      for state in outer
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(outer, outer[1:])
    )
    and bool(centerline)
    and outer[0].x_m > centerline[0].x_m + request.position_tolerance_m
    and (
      max(state.k_minus for state in outer)
      - min(state.k_minus for state in outer)
      > request.invariant_tolerance
    )
  )

  incoming_pressure_verified = bool(
    incoming
    and all(
      isfinite(float(sample.total_pressure_Pa))
      and sample.total_pressure_Pa > 0.0
      and (
        request.variable_total_pressure
        or _pressure_matches(
          sample.total_pressure_Pa,
          request.total_pressure_Pa,
          pressure_tolerance=request.pressure_tolerance,
        )
      )
      for sample in incoming
    )
  )

  source_strip = remesh.source_strip
  source_node_count = 0
  source_cell_count = 0
  source_topology = _empty_topology()
  source_topology_verified = False
  source_sampling_verified = False
  source_pressure_verified = False
  if isinstance(source_strip, MocSourceCharacteristicStripResult):
    source_node_count = len(source_strip.nodes)
    source_cell_count = len(source_strip.cells)
    try:
      source_topology = validate_moc_mesh(source_strip.cells)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      source_topology = _empty_topology()
    source_topology_verified = bool(
      source_strip.converged
      and source_topology.connected
      and source_topology.forms_closed_zone
      and source_topology.nonmanifold_edge_count == 0
    )
    source_samples = tuple(
      (state, pressure)
      for state, pressure in zip(
        centerline,
        request.centerline_total_pressure_Pa,
        strict=True,
      )
    ) + tuple(
      (state, pressure)
      for state, pressure in zip(
        outer,
        request.outer_total_pressure_Pa,
        strict=True,
      )
    )
    sampled_states_verified = True
    sampled_pressures_verified = True
    if not source_samples:
      sampled_states_verified = False
      sampled_pressures_verified = False
    for state, expected_total_pressure in source_samples:
      try:
        sampled_state = source_strip.state_at(
          (state.x_m, state.y_m),
          position_tolerance_m=request.position_tolerance_m,
        )
        sampled_pressure = source_strip.static_pressure_at(
          (state.x_m, state.y_m),
          position_tolerance_m=request.position_tolerance_m,
        )
        sampled_total_pressure = source_strip.total_pressure_at(
          (state.x_m, state.y_m),
          position_tolerance_m=request.position_tolerance_m,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        sampled_state = None
        sampled_pressure = None
        sampled_total_pressure = None
      sampled_states_verified = sampled_states_verified and bool(
        _caustic_state_matches(
          sampled_state,
          state,
          position_tolerance_m=request.position_tolerance_m,
          state_tolerance=request.invariant_tolerance,
        )
      )
      sampled_pressures_verified = sampled_pressures_verified and bool(
        sampled_pressure is not None
        and isfinite(float(sampled_pressure))
        and float(sampled_pressure) > 0.0
        and sampled_total_pressure is not None
        and isfinite(float(sampled_total_pressure))
        and float(sampled_total_pressure) > 0.0
        and _pressure_matches(
          sampled_total_pressure,
          expected_total_pressure,
          pressure_tolerance=request.pressure_tolerance,
        )
      )
    source_sampling_verified = bool(
      source_strip.converged
      and sampled_states_verified
      and sampled_pressures_verified
    )
    source_pressure_verified = bool(
      _pressure_matches(
        source_strip.total_pressure_Pa,
        request.centerline_total_pressure_Pa[0],
        pressure_tolerance=request.pressure_tolerance,
      )
      and len(source_strip.plus_source_total_pressure_Pa)
      == len(request.centerline_total_pressure_Pa)
      and len(source_strip.minus_source_total_pressure_Pa)
      == len(request.outer_total_pressure_Pa)
      and all(
        _pressure_matches(actual, expected, pressure_tolerance=request.pressure_tolerance)
        for actual, expected in zip(
          source_strip.plus_source_total_pressure_Pa,
          request.centerline_total_pressure_Pa,
          strict=True,
        )
      )
      and all(
        _pressure_matches(actual, expected, pressure_tolerance=request.pressure_tolerance)
        for actual, expected in zip(
          source_strip.minus_source_total_pressure_Pa,
          request.outer_total_pressure_Pa,
          strict=True,
        )
      )
    )
  total_pressure_verified = bool(
    incoming_pressure_verified and source_pressure_verified
  )
  bounded_remesh_verified = bool(
    result_status_verified
    and incoming_trace_verified
    and polarity_verified
    and reflection_seam_verified
    and centerline_source_verified
    and outer_source_verified
    and total_pressure_verified
    and source_topology_verified
    and source_sampling_verified
  )

  if not incoming_trace_verified or not polarity_verified:
    status = MocReflectedDomainRemeshMeasurementStatus.INCOMING_TRACE_FAILURE
    message = (
      'incoming reflected C- trace or declared polarity failed independent '
      'measurement'
    )
  elif not reflection_seam_verified:
    status = MocReflectedDomainRemeshMeasurementStatus.REFLECTION_SEAM_FAILURE
    message = (
      'incoming reflected endpoint, first centerline state, or total-pressure '
      'seam failed independent measurement'
    )
  elif (
    not centerline_source_verified
    or not outer_source_verified
    or not total_pressure_verified
  ):
    status = MocReflectedDomainRemeshMeasurementStatus.SOURCE_FAILURE
    message = (
      'reflected-domain centerline/outer source rows or source-row pressure '
      'lineage failed independent measurement'
    )
  elif not source_topology_verified or not source_sampling_verified:
    status = MocReflectedDomainRemeshMeasurementStatus.FIELD_FAILURE
    message = (
      'reflected-domain source topology or state/pressure sampling failed '
      'independent measurement'
    )
  elif not result_status_verified:
    status = MocReflectedDomainRemeshMeasurementStatus.FIELD_FAILURE
    message = (
      'the remesh result did not report a converged bounded source field'
    )
  else:
    status = MocReflectedDomainRemeshMeasurementStatus.CONVERGED
    message = (
      'bounded reflected-domain Cauchy remesh passed independent trace, seam, '
      'source-row, pressure, topology, and sampling checks; physical closure '
      'and chain promotion remain separate pending gates'
    )

  return _reflected_domain_remesh_measurement_failure(
    status,
    remesh_status=remesh_status,
    incoming_trace_polarity=incoming_trace_polarity,
    incoming_trace_sample_count=incoming_count,
    centerline_source_count=centerline_count,
    outer_source_count=outer_count,
    source_node_count=source_node_count,
    source_cell_count=source_cell_count,
    source_topology=source_topology,
    result_status_verified=result_status_verified,
    incoming_trace_verified=incoming_trace_verified,
    polarity_verified=polarity_verified,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    total_pressure_verified=total_pressure_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_remesh_verified=bounded_remesh_verified,
    message=message,
  )
####


def _reflected_domain_outer_source_measurement_failure(
  status: MocReflectedDomainOuterSourceMeasurementStatus,
  *,
  solver_status: str | None = None,
  centerline_source_count: int = 0,
  outer_source_count: int = 0,
  boundary_point_count: int = 0,
  source_node_count: int = 0,
  source_cell_count: int = 0,
  source_topology: MocTopologyResult | None = None,
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None,
  result_status_verified: bool = False,
  seed_verified: bool = False,
  centerline_source_verified: bool = False,
  outer_source_verified: bool = False,
  pressure_lineage_verified: bool = False,
  ambient_boundary_verified: bool = False,
  source_topology_verified: bool = False,
  source_sampling_verified: bool = False,
  bounded_source_verified: bool = False,
  message: str,
) -> MocReflectedDomainOuterSourceMeasurement:
  return MocReflectedDomainOuterSourceMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_OUTER_SOURCE_OPERATOR_ID,
    solver_status=solver_status,
    centerline_source_count=centerline_source_count,
    outer_source_count=outer_source_count,
    boundary_point_count=boundary_point_count,
    source_node_count=source_node_count,
    source_cell_count=source_cell_count,
    source_topology=(_empty_topology() if source_topology is None else source_topology),
    ambient_boundary=ambient_boundary,
    result_status_verified=result_status_verified,
    seed_verified=seed_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_source_verified=bounded_source_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status='independent-reflected-domain-outer-source-audit; not-accepted',
    message=message,
  )


def measure_moc_reflected_domain_outer_source_curve(
  result: MocReflectedDomainOuterSourceResult,
) -> MocReflectedDomainOuterSourceMeasurement:
  """Independently audit a solver-generated reflected outer source curve.

  The operator reconstructs the ambient boundary and source strip from the
  returned rows.  It intentionally does not trust the solver's convergence,
  source-curve, or field flags, and it never treats this source domain as a
  closed or promotable shock cell.
  """

  if not isinstance(result, MocReflectedDomainOuterSourceResult):
    return _reflected_domain_outer_source_measurement_failure(
      MocReflectedDomainOuterSourceMeasurementStatus.INVALID_INPUT,
      message='result must be a MocReflectedDomainOuterSourceResult',
    )

  solver_status = getattr(result.status, 'value', str(result.status))
  centerline = tuple(result.centerline_source_states)
  outer = tuple(result.outer_source_states)
  centerline_pressures = tuple(result.centerline_total_pressure_Pa)
  outer_pressures = tuple(result.outer_total_pressure_Pa)
  centerline_count = len(centerline)
  outer_count = len(outer)
  tolerance = result.position_tolerance_m
  state_tolerance = result.invariant_tolerance
  pressure_tolerance = result.pressure_tolerance
  ambient_pressure = result.ambient_pressure_Pa

  result_status_verified = (
    result.status is MocReflectedDomainOuterSourceStatus.CONVERGED
  )
  centerline_verified = bool(
    centerline_count >= 3
    and all(isinstance(state, CharacteristicState) for state in centerline)
    and all(
      abs(state.y_m - result.target_centerline_y_m) <= tolerance
      and abs(state.theta_rad - result.target_centerline_flow_angle_rad)
      <= state_tolerance
      for state in centerline
    )
    and all(
      right.x_m > left.x_m + tolerance
      for left, right in zip(centerline, centerline[1:])
    )
    and all(
      abs(state.gamma - centerline[0].gamma) <= state_tolerance
      for state in centerline
    )
  )
  outer_verified = bool(
    outer_count == centerline_count
    and outer_count >= 3
    and centerline
    and all(isinstance(state, CharacteristicState) for state in outer)
    and all(
      state.y_m > result.target_centerline_y_m + tolerance
      and abs(state.gamma - centerline[0].gamma) <= state_tolerance
      for state in outer
    )
    and all(
      right.x_m > left.x_m + tolerance
      for left, right in zip(outer, outer[1:])
    )
    and outer[0].x_m > centerline[0].x_m + tolerance
    and max(state.k_minus for state in outer)
    - min(state.k_minus for state in outer)
    > state_tolerance
  )

  reference_pressure = result.reference_total_pressure_Pa
  previous_pressure = result.previous_boundary_total_pressure_Pa
  seed_verified = bool(
    isinstance(result.previous_boundary_state, CharacteristicState)
    and reference_pressure is not None
    and previous_pressure is not None
    and ambient_pressure is not None
    and centerline
    and _pressure_matches(
      centerline_pressures[0] if centerline_pressures else None,
      reference_pressure,
      pressure_tolerance=pressure_tolerance,
    )
    and _pressure_matches(
      outer_pressures[0] if outer_pressures else None,
      previous_pressure,
      pressure_tolerance=pressure_tolerance,
    )
    and result.previous_boundary_state.y_m
    > result.target_centerline_y_m + tolerance
    and result.previous_boundary_state.x_m
    > centerline[0].x_m + tolerance
    and abs(
      (
        previous_pressure
        / (
          1.0
          + 0.5
          * (result.previous_boundary_state.gamma - 1.0)
          * result.previous_boundary_state.mach
          * result.previous_boundary_state.mach
        )
        ** (
          result.previous_boundary_state.gamma
          / (result.previous_boundary_state.gamma - 1.0)
        )
        - ambient_pressure
      )
      / ambient_pressure
    )
    <= pressure_tolerance
  )
  pressure_lineage_verified = bool(
    len(centerline_pressures) == centerline_count
    and len(outer_pressures) == outer_count
    and all(
      isfinite(float(value)) and float(value) > 0.0
      for value in (*centerline_pressures, *outer_pressures)
    )
    and reference_pressure is not None
    and previous_pressure is not None
    and _pressure_matches(
      centerline_pressures[0] if centerline_pressures else None,
      reference_pressure,
      pressure_tolerance=pressure_tolerance,
    )
    and _pressure_matches(
      outer_pressures[0] if outer_pressures else None,
      previous_pressure,
      pressure_tolerance=pressure_tolerance,
    )
    and all(
      _pressure_matches(
        outer_pressures[index],
        centerline_pressures[index],
        pressure_tolerance=pressure_tolerance,
      )
      for index in range(1, min(centerline_count, outer_count))
    )
  )

  ambient_boundary: MocAmbientPressureBoundaryResult | None = None
  if (
    outer_verified
    and pressure_lineage_verified
    and ambient_pressure is not None
  ):
    ambient_boundary = validate_ambient_pressure_boundary(
      tuple(
        MocAmbientBoundarySample(
          point_m=(state.x_m, state.y_m),
          state=state,
          total_pressure_Pa=pressure,
        )
        for state, pressure in zip(outer, outer_pressures, strict=True)
      ),
      ambient_pressure,
      position_tolerance_m=tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=pressure_tolerance,
    )
  ambient_boundary_verified = bool(
    ambient_boundary is not None and ambient_boundary.converged
  )

  recomputed_strip: MocSourceCharacteristicStripResult | None = None
  if centerline_verified and outer_verified and pressure_lineage_verified:
    recomputed_strip = assemble_source_characteristic_strip_with_source_pressures(
      centerline,
      outer,
      centerline_pressures,
      outer_pressures,
      position_tolerance_m=tolerance,
      invariant_tolerance=state_tolerance,
    )
  source_topology = (
    _empty_topology()
    if recomputed_strip is None
    else recomputed_strip.topology
  )
  source_topology_verified = bool(
    recomputed_strip is not None
    and recomputed_strip.converged
    and source_topology.connected
    and source_topology.forms_closed_zone
    and source_topology.nonmanifold_edge_count == 0
  )
  source_sampling_verified = bool(
    source_topology_verified
    and recomputed_strip is not None
    and all(
      _caustic_state_matches(
        recomputed_strip.state_at(
          (state.x_m, state.y_m),
          position_tolerance_m=tolerance,
        ),
        state,
        position_tolerance_m=tolerance,
        state_tolerance=state_tolerance,
      )
      and _pressure_matches(
        recomputed_strip.total_pressure_at(
          (state.x_m, state.y_m),
          position_tolerance_m=tolerance,
        ),
        pressure,
        pressure_tolerance=pressure_tolerance,
      )
      for state, pressure in (
        *zip(centerline, centerline_pressures, strict=True),
        *zip(outer, outer_pressures, strict=True),
      )
    )
  )
  bounded_source_verified = bool(
    result_status_verified
    and seed_verified
    and centerline_verified
    and outer_verified
    and pressure_lineage_verified
    and ambient_boundary_verified
    and source_topology_verified
    and source_sampling_verified
  )

  if not seed_verified:
    status = MocReflectedDomainOuterSourceMeasurementStatus.SEED_FAILURE
    message = 'previous ambient outer-boundary seed failed independent measurement'
  elif not centerline_verified or not outer_verified or not pressure_lineage_verified:
    status = MocReflectedDomainOuterSourceMeasurementStatus.BOUNDARY_FAILURE
    message = 'generated source rows or pressure lineage failed independent measurement'
  elif not ambient_boundary_verified:
    status = MocReflectedDomainOuterSourceMeasurementStatus.BOUNDARY_FAILURE
    message = 'generated outer source curve failed independent ambient acceptance'
  elif not source_topology_verified or not source_sampling_verified:
    status = MocReflectedDomainOuterSourceMeasurementStatus.FIELD_FAILURE
    message = 'recomputed source characteristic strip failed independent measurement'
  elif not result_status_verified:
    status = MocReflectedDomainOuterSourceMeasurementStatus.FIELD_FAILURE
    message = 'outer-source result did not report a converged generated source'
  else:
    status = MocReflectedDomainOuterSourceMeasurementStatus.CONVERGED
    message = (
      'ambient outer-source curve and bounded characteristic strip passed '
      'independent row, pressure, boundary, topology, and sampling checks; '
      'shock-cell closure and promotion remain pending'
    )

  return _reflected_domain_outer_source_measurement_failure(
    status,
    solver_status=solver_status,
    centerline_source_count=centerline_count,
    outer_source_count=outer_count,
    boundary_point_count=len(result.point_results),
    source_node_count=(0 if recomputed_strip is None else recomputed_strip.node_count),
    source_cell_count=(0 if recomputed_strip is None else recomputed_strip.cell_count),
    source_topology=source_topology,
    ambient_boundary=ambient_boundary,
    result_status_verified=result_status_verified,
    seed_verified=seed_verified,
    centerline_source_verified=centerline_verified,
    outer_source_verified=outer_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_source_verified=bounded_source_verified,
    message=message,
  )
####


def _reflected_domain_alternating_source_measurement_failure(
  status: MocReflectedDomainAlternatingSourceMeasurementStatus,
  *,
  solver_status: str | None = None,
  incoming_trace_sample_count: int = 0,
  source_sample_count: int = 0,
  source_node_count: int = 0,
  source_cell_count: int = 0,
  source_topology: MocTopologyResult | None = None,
  incoming_trace_verified: bool = False,
  polarity_verified: bool = False,
  seed_verified: bool = False,
  reflection_anchor_verified: bool = False,
  centerline_recomputed_verified: bool = False,
  boundary_recomputed_verified: bool = False,
  pressure_lineage_verified: bool = False,
  ambient_boundary_verified: bool = False,
  alternating_seam_verified: bool = False,
  source_topology_verified: bool = False,
  source_sampling_verified: bool = False,
  bounded_source_verified: bool = False,
  message: str,
) -> MocReflectedDomainAlternatingSourceMeasurement:
  return MocReflectedDomainAlternatingSourceMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_ALTERNATING_SOURCE_OPERATOR_ID,
    solver_status=solver_status,
    incoming_trace_sample_count=incoming_trace_sample_count,
    source_sample_count=source_sample_count,
    source_node_count=source_node_count,
    source_cell_count=source_cell_count,
    source_topology=(_empty_topology() if source_topology is None else source_topology),
    incoming_trace_verified=incoming_trace_verified,
    polarity_verified=polarity_verified,
    seed_verified=seed_verified,
    reflection_anchor_verified=reflection_anchor_verified,
    centerline_recomputed_verified=centerline_recomputed_verified,
    boundary_recomputed_verified=boundary_recomputed_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    alternating_seam_verified=alternating_seam_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_source_verified=bounded_source_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status='independent-alternating-reflected-domain-audit; not-accepted',
    message=message,
  )
####


def measure_moc_reflected_domain_alternating_source(
  result: MocReflectedDomainAlternatingSourceResult,
) -> MocReflectedDomainAlternatingSourceMeasurement:
  """Independently audit an alternating-family reflected source band.

  The operator recomputes the incoming reflection, every local ``C-`` and
  ``C+`` step, ambient boundary acceptance, and the two-triangle topology from
  raw rows.  It does not use the solver's cached convergence or promotion
  properties as evidence.
  """

  if not isinstance(result, MocReflectedDomainAlternatingSourceResult):
    return _reflected_domain_alternating_source_measurement_failure(
      MocReflectedDomainAlternatingSourceMeasurementStatus.INVALID_INPUT,
      message='result must be a MocReflectedDomainAlternatingSourceResult',
    )

  solver_status = getattr(result.status, 'value', str(result.status))
  patch = result.reflection_patch
  centerline = tuple(result.centerline_source_states)
  outer = tuple(result.outer_source_states)
  centerline_pressures = tuple(result.centerline_total_pressure_Pa)
  outer_pressures = tuple(result.outer_total_pressure_Pa)
  source_count = len(centerline)
  trace_count = 0 if patch is None else len(patch.outgoing_trace_states)
  tolerance = result.position_tolerance_m
  trace_forward_tolerance = result.trace_forward_tolerance_m
  state_tolerance = result.invariant_tolerance
  pressure_tolerance = result.pressure_tolerance
  ambient_pressure = result.ambient_pressure_Pa

  if patch is None or not isinstance(
    patch,
    MocTerminalReflectionPatchResult,
  ):
    return _reflected_domain_alternating_source_measurement_failure(
      MocReflectedDomainAlternatingSourceMeasurementStatus.INVALID_INPUT,
      solver_status=solver_status,
      source_sample_count=source_count,
      message='alternating source result has no valid reflection patch',
    )
  incoming = patch.outgoing_trace_samples
  incoming_validation = validate_characteristic_trace(
    incoming,
    CharacteristicFamily.MINUS,
    position_tolerance_m=tolerance,
    forward_position_tolerance_m=trace_forward_tolerance,
    invariant_tolerance=state_tolerance,
  )
  incoming_trace_verified = bool(
    patch.converged and incoming_validation.converged
  )
  polarity = classify_reflected_trace_polarity(
    incoming,
    target_centerline_y_m=result.target_centerline_y_m,
    target_centerline_flow_angle_rad=result.target_centerline_flow_angle_rad,
    position_tolerance_m=tolerance,
    forward_position_tolerance_m=trace_forward_tolerance,
    invariant_tolerance=state_tolerance,
  )
  polarity_verified = bool(incoming_trace_verified and polarity.converged)

  seed = result.outer_seed_state
  seed_pressure = result.outer_seed_total_pressure_Pa
  seed_verified = bool(
    isinstance(seed, CharacteristicState)
    and seed_pressure is not None
    and ambient_pressure is not None
    and incoming
    and _caustic_state_matches(
      seed,
      incoming[0].state,
      position_tolerance_m=tolerance,
      state_tolerance=state_tolerance,
    )
    and _pressure_matches(
      seed_pressure,
      incoming[0].total_pressure_Pa,
      pressure_tolerance=pressure_tolerance,
    )
    and seed.y_m > result.target_centerline_y_m + tolerance
    and abs(
      _static_pressure_from_total_pressure_for_measurement(seed, seed_pressure)
      - ambient_pressure
    ) / ambient_pressure <= pressure_tolerance
  )

  row_shape_verified = bool(
    source_count >= 3
    and len(outer) == source_count
    and len(centerline_pressures) == source_count
    and len(outer_pressures) == source_count
    and all(isinstance(state, CharacteristicState) for state in (*centerline, *outer))
    and all(
      isfinite(float(value)) and float(value) > 0.0
      for value in (*centerline_pressures, *outer_pressures)
    )
  )
  pressure_lineage_verified = bool(
    row_shape_verified
    and seed_pressure is not None
    and incoming
    and _pressure_matches(
      centerline_pressures[0],
      incoming[-1].total_pressure_Pa,
      pressure_tolerance=pressure_tolerance,
    )
    and _pressure_matches(
      outer_pressures[0],
      centerline_pressures[0],
      pressure_tolerance=pressure_tolerance,
    )
    and all(
      _pressure_matches(
        outer_pressures[index],
        centerline_pressures[index],
        pressure_tolerance=pressure_tolerance,
      )
      for index in range(source_count)
    )
  )

  reflection_anchor_verified = False
  centerline_recomputed_verified = False
  boundary_recomputed_verified = False
  if (
    row_shape_verified
    and seed_verified
    and pressure_lineage_verified
    and isinstance(seed, CharacteristicState)
    and seed_pressure is not None
    and ambient_pressure is not None
    and incoming
  ):
    previous_outer = seed
    previous_axis: CharacteristicState | None = None
    centerline_recomputed_verified = True
    boundary_recomputed_verified = True
    for index in range(source_count):
      axis_result = centerline_characteristic_point(
        previous_outer,
        CharacteristicFamily.MINUS,
        position_tolerance_m=tolerance,
        invariant_tolerance=state_tolerance,
      )
      expected_axis = axis_result.state
      axis_matches = bool(
        axis_result.converged
        and expected_axis is not None
        and _caustic_state_matches(
          centerline[index],
          expected_axis,
          position_tolerance_m=tolerance,
          state_tolerance=state_tolerance,
        )
        and abs(centerline[index].y_m - result.target_centerline_y_m) <= tolerance
        and abs(centerline[index].theta_rad - result.target_centerline_flow_angle_rad)
        <= state_tolerance
        and (
          previous_axis is None
          or centerline[index].x_m > previous_axis.x_m + tolerance
        )
      )
      centerline_recomputed_verified = centerline_recomputed_verified and axis_matches
      if index == 0:
        reflection_anchor_verified = bool(
          axis_matches
          and _caustic_state_matches(
            centerline[index],
            incoming[-1].state,
            position_tolerance_m=tolerance,
            state_tolerance=state_tolerance,
          )
        )
      if not axis_matches:
        boundary_recomputed_verified = False
        break
      boundary_result = solve_ambient_pressure_free_boundary_point(
        centerline[index],
        previous_outer,
        CharacteristicFamily.PLUS,
        total_pressure_Pa=centerline_pressures[index],
        ambient_pressure_Pa=ambient_pressure,
        position_tolerance_m=tolerance,
        pressure_tolerance=pressure_tolerance,
      )
      expected_outer = boundary_result.state
      boundary_matches = bool(
        boundary_result.converged
        and expected_outer is not None
        and _caustic_state_matches(
          outer[index],
          expected_outer,
          position_tolerance_m=tolerance,
          state_tolerance=state_tolerance,
        )
        and outer[index].x_m > previous_outer.x_m + tolerance
        and outer[index].x_m > centerline[index].x_m + tolerance
        and outer[index].y_m > result.target_centerline_y_m + tolerance
      )
      boundary_recomputed_verified = boundary_recomputed_verified and boundary_matches
      if not boundary_matches:
        break
      previous_axis = centerline[index]
      previous_outer = outer[index]

  alternating_seam_verified = bool(
    row_shape_verified
    and all(
      abs(outer[index].k_plus - centerline[index].k_plus) <= state_tolerance
      for index in range(source_count)
    )
    and all(
      abs(centerline[index + 1].k_minus - outer[index].k_minus)
      <= state_tolerance
      for index in range(source_count - 1)
    )
  )

  recomputed_cells: list[MocCharacteristicCell] = []
  if row_shape_verified:
    try:
      for index in range(source_count - 1):
        recomputed_cells.extend((
          MocCharacteristicCell(
            cell_index=len(recomputed_cells),
            cell_kind='alternating-axis-step',
            vertices_xr_m=(
              (centerline[index].x_m, centerline[index].y_m),
              (centerline[index + 1].x_m, centerline[index + 1].y_m),
              (outer[index].x_m, outer[index].y_m),
            ),
            centerline_indices=(index, index + 1),
            boundary_indices=(index,),
          ),
          MocCharacteristicCell(
            cell_index=len(recomputed_cells) + 1,
            cell_kind='alternating-boundary-step',
            vertices_xr_m=(
              (centerline[index + 1].x_m, centerline[index + 1].y_m),
              (outer[index + 1].x_m, outer[index + 1].y_m),
              (outer[index].x_m, outer[index].y_m),
            ),
            centerline_indices=(index + 1,),
            boundary_indices=(index, index + 1),
          ),
        ))
    except (TypeError, ValueError):
      recomputed_cells = []
  source_topology = (
    _empty_topology()
    if not recomputed_cells
    else validate_moc_mesh(recomputed_cells)
  )
  source_topology_verified = bool(
    row_shape_verified
    and len(recomputed_cells) == 2 * (source_count - 1)
    and source_topology.connected
    and source_topology.forms_closed_zone
    and source_topology.nonmanifold_edge_count == 0
  )

  recomputed_ambient_boundary: MocAmbientPressureBoundaryResult | None = None
  if row_shape_verified and ambient_pressure is not None:
    recomputed_ambient_boundary = validate_ambient_pressure_boundary(
      tuple(
        MocAmbientBoundarySample(
          point_m=(state.x_m, state.y_m),
          state=state,
          total_pressure_Pa=pressure,
        )
        for state, pressure in zip(outer, outer_pressures, strict=True)
      ),
      ambient_pressure,
      position_tolerance_m=tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=pressure_tolerance,
    )
  ambient_boundary_verified = bool(
    recomputed_ambient_boundary is not None
    and recomputed_ambient_boundary.converged
  )

  source_sampling_verified = False
  if source_topology_verified:
    source_sampling_verified = all(
      _caustic_state_matches(
        result.state_at((state.x_m, state.y_m)),
        state,
        position_tolerance_m=tolerance,
        state_tolerance=state_tolerance,
      )
      and _pressure_matches(
        result.total_pressure_at((state.x_m, state.y_m)),
        pressure,
        pressure_tolerance=pressure_tolerance,
      )
      for state, pressure in (
        *zip(centerline, centerline_pressures, strict=True),
        *zip(outer, outer_pressures, strict=True),
      )
    )
    if source_sampling_verified:
      source_sampling_verified = all(
        result.state_at(
          (
            sum(vertex[0] for vertex in cell.vertices_xr_m) / len(cell.vertices_xr_m),
            sum(vertex[1] for vertex in cell.vertices_xr_m) / len(cell.vertices_xr_m),
          )
        ) is not None
        for cell in recomputed_cells
      ) and result.state_at(
        (centerline[0].x_m, -max(1.0, 10.0 * tolerance))
      ) is None

  result_status_verified = result.status is MocReflectedDomainAlternatingSourceStatus.CONVERGED
  bounded_source_verified = bool(
    result_status_verified
    and incoming_trace_verified
    and polarity_verified
    and seed_verified
    and reflection_anchor_verified
    and centerline_recomputed_verified
    and boundary_recomputed_verified
    and pressure_lineage_verified
    and ambient_boundary_verified
    and alternating_seam_verified
    and source_topology_verified
    and source_sampling_verified
  )
  if not incoming_trace_verified or not polarity_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.INCOMING_TRACE_FAILURE
    message = 'incoming reflected trace or its polarity failed independent measurement'
  elif not seed_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.SEED_FAILURE
    message = 'alternating outer seed failed independent measurement'
  elif not reflection_anchor_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.ANCHOR_FAILURE
    message = 'first alternating C- reflection failed independent anchor measurement'
  elif not centerline_recomputed_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.CENTERLINE_FAILURE
    message = 'alternating centerline row failed independent characteristic measurement'
  elif not boundary_recomputed_verified or not ambient_boundary_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.BOUNDARY_FAILURE
    message = 'alternating ambient boundary failed independent characteristic or pressure measurement'
  elif not alternating_seam_verified or not source_topology_verified or not source_sampling_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.FIELD_FAILURE
    message = 'alternating source-band seam, topology, or bounded sampling failed independent measurement'
  elif not result_status_verified:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.FIELD_FAILURE
    message = 'alternating source result did not report a converged bounded band'
  else:
    status = MocReflectedDomainAlternatingSourceMeasurementStatus.CONVERGED
    message = (
      'alternating C-/C+ source band passed independent trace, seam, ambient, '
      'topology, and bounded-sampling checks; shock closure and promotion remain pending'
    )
  return _reflected_domain_alternating_source_measurement_failure(
    status,
    solver_status=solver_status,
    incoming_trace_sample_count=trace_count,
    source_sample_count=source_count,
    source_node_count=(2 * source_count if row_shape_verified else 0),
    source_cell_count=len(recomputed_cells),
    source_topology=source_topology,
    incoming_trace_verified=incoming_trace_verified,
    polarity_verified=polarity_verified,
    seed_verified=seed_verified,
    reflection_anchor_verified=reflection_anchor_verified,
    centerline_recomputed_verified=centerline_recomputed_verified,
    boundary_recomputed_verified=boundary_recomputed_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    alternating_seam_verified=alternating_seam_verified,
    source_topology_verified=source_topology_verified,
    source_sampling_verified=source_sampling_verified,
    bounded_source_verified=bounded_source_verified,
    message=message,
  )
####


def _reflected_domain_alternating_physical_field_measurement_failure(
  status: MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus,
  *,
  solver_status: str | None = None,
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None = None,
  field_measurement: MocPhysicalFieldChainMeasurement | None = None,
  source_field_verified: bool = False,
  attachment_point_verified: bool = False,
  attachment_pressure_verified: bool = False,
  zero_strength_attachment_verified: bool = False,
  envelope_verified: bool = False,
  shock_curve_verified: bool = False,
  physical_field_verified: bool = False,
  state_sampling_verified: bool = False,
  upstream_coupling_verified: bool = False,
  incoming_handoff_verified: bool = False,
  bounded_physical_field_verified: bool = False,
  compression_amplitude_rad: float | None = None,
  shock_sample_count: int = 0,
  message: str,
) -> MocReflectedDomainAlternatingPhysicalFieldMeasurement:
  return MocReflectedDomainAlternatingPhysicalFieldMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_OPERATOR_ID,
    solver_status=solver_status,
    source_measurement=source_measurement,
    field_measurement=field_measurement,
    source_field_verified=source_field_verified,
    attachment_point_verified=attachment_point_verified,
    attachment_pressure_verified=attachment_pressure_verified,
    zero_strength_attachment_verified=zero_strength_attachment_verified,
    envelope_verified=envelope_verified,
    shock_curve_verified=shock_curve_verified,
    physical_field_verified=physical_field_verified,
    state_sampling_verified=state_sampling_verified,
    upstream_coupling_verified=upstream_coupling_verified,
    incoming_handoff_verified=incoming_handoff_verified,
    bounded_physical_field_verified=bounded_physical_field_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    compression_amplitude_rad=compression_amplitude_rad,
    shock_sample_count=shock_sample_count,
    claim_status=(
      'independent-alternating-source-physical-field-audit; '
      'canonical-reflected-free-boundary-not-accepted'
    ),
    message=message,
  )
####


def measure_moc_reflected_domain_alternating_physical_field(
  result: MocReflectedDomainAlternatingPhysicalFieldResult,
) -> MocReflectedDomainAlternatingPhysicalFieldMeasurement:
  """Independently audit an alternating source band and its shock field.

  The source band is remeasured first.  The physical field is then passed
  through the raw ambient-closed-field measurement, while the shock's
  upstream samples and local compression envelope are re-evaluated directly
  from the source band.  Solver status flags are reported but never used as
  proof.  A successful measurement is research evidence only.
  """

  if not isinstance(
    result,
    MocReflectedDomainAlternatingPhysicalFieldResult,
  ):
    return _reflected_domain_alternating_physical_field_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.INVALID_INPUT,
      message=(
        'result must be a '
        'MocReflectedDomainAlternatingPhysicalFieldResult'
      ),
    )

  solver_status = getattr(result.status, 'value', str(result.status))
  source_band = result.source_band
  source_measurement = (
    None
    if source_band is None
    else measure_moc_reflected_domain_alternating_source(source_band)
  )
  source_field_verified = bool(
    source_measurement is not None and source_measurement.converged
  )
  field_result = result.field_result
  physical_field = None if field_result is None else field_result.field
  field_measurement = None
  if isinstance(physical_field, MocPhysicalPostShockFieldResult):
    field_measurement = measure_moc_ambient_closed_physical_field_chain(
      (physical_field,),
    )

  attachment = None if field_result is None else field_result.ambient_attachment
  shock = None if attachment is None else attachment.shock
  shock_sample_count = 0 if shock is None else len(shock.shock_points_m)
  source_index = result.outer_source_index
  source_state = None
  source_pressure = None
  source_sampling_position_tolerance = result.position_tolerance_m
  attachment_point_verified = False
  attachment_pressure_verified = False
  zero_strength_attachment_verified = bool(
    attachment is not None and attachment.zero_strength_attachment
  )
  envelope_verified = False
  compression_profile: MocReflectedTraceCompressionProfile | None = None
  upstream_coupling_verified = False
  incoming_handoff_verified = False

  if source_band is not None and result.attachment_source == (
    'outer-seed-reflection-interface'
  ):
    source_state = source_band.outer_seed_state
  elif (
    source_band is not None
    and isinstance(source_index, int)
    and not isinstance(source_index, bool)
    and 0 <= source_index < len(source_band.outer_source_states)
  ):
    source_state = source_band.outer_source_states[source_index]
  if source_band is not None and source_state is not None:
    source_pressure = source_band.static_pressure_at(
      (source_state.x_m, source_state.y_m),
      position_tolerance_m=source_sampling_position_tolerance,
    )

  if (
    source_band is not None
    and source_state is not None
    and result.start_point_m is not None
    and shock is not None
    and shock.shock_points_m
    and shock.upstream_states
  ):
    attachment_point_verified = bool(
      _caustic_points_match(
        (result.start_point_m,),
        (shock.shock_points_m[0],),
        position_tolerance_m=source_sampling_position_tolerance,
      )
      and _caustic_state_matches(
        shock.upstream_states[0],
        source_state,
        position_tolerance_m=source_sampling_position_tolerance,
        state_tolerance=source_band.invariant_tolerance,
      )
    )
    attachment_pressure_verified = bool(
      source_pressure is not None
      and source_band.ambient_pressure_Pa is not None
      and _pressure_matches(
        source_pressure,
        source_band.ambient_pressure_Pa,
        pressure_tolerance=source_band.pressure_tolerance,
      )
      and shock.upstream_pressure_Pa
      and _pressure_matches(
        shock.upstream_pressure_Pa[0],
        source_pressure,
        pressure_tolerance=source_band.pressure_tolerance,
      )
    )

  if (
    source_band is not None
    and source_state is not None
    and result.compression_amplitude_rad is not None
    and shock is not None
    and len(shock.shock_points_m) == len(shock.upstream_states)
    and len(shock.shock_points_m) == len(shock.downstream_flow_angles_rad)
  ):
    denominator = source_state.y_m - source_band.target_centerline_y_m
    if denominator > source_band.position_tolerance_m:
      envelope_verified = True
      if result.continuation_law == (
        'reflected-trace-referenced-compression-envelope'
      ):
        try:
          if (
            source_band.reflection_patch is None
            or result.compression_amplitude_rad is None
          ):
            raise ValueError(
              'reflected trace and compression amplitude are required'
            )
          compression_profile = build_reflected_trace_compression_profile(
            source_band.reflection_patch.outgoing_trace_samples,
            result.compression_amplitude_rad,
            target_centerline_y_m=source_band.target_centerline_y_m,
            target_centerline_flow_angle_rad=(
              source_band.target_centerline_flow_angle_rad
            ),
            envelope_skew=result.compression_envelope_skew,
          )
          envelope_verified = _caustic_state_matches(
            source_state,
            compression_profile.source_trace[0].state,
            position_tolerance_m=source_sampling_position_tolerance,
            state_tolerance=source_band.invariant_tolerance,
          )
        except (ArithmeticError, FloatingPointError, TypeError, ValueError):
          compression_profile = None
          envelope_verified = False
      for index, (point, target_angle) in enumerate(zip(
        shock.shock_points_m,
        shock.downstream_flow_angles_rad,
        strict=True,
      )):
        fraction = (
          point[1] - source_band.target_centerline_y_m
        ) / denominator
        if fraction < -1.0e-8 or fraction > 1.0 + 1.0e-8:
          envelope_verified = False
          break
        fraction = max(0.0, min(1.0, fraction))
        if compression_profile is not None:
          try:
            expected_angle = compression_profile.flow_angle_at(index, point)
          except (ArithmeticError, FloatingPointError, TypeError, ValueError):
            envelope_verified = False
            break
        elif index == len(shock.shock_points_m) - 1:
          expected_angle = source_band.target_centerline_flow_angle_rad
        else:
          state = source_band.state_at(
            point,
            position_tolerance_m=source_sampling_position_tolerance,
          )
          if state is None:
            envelope_verified = False
            break
          expected_angle = state.theta_rad + float(
            result.compression_amplitude_rad
          ) * 4.0 * fraction * (1.0 - fraction) * (
            1.0 + result.compression_envelope_skew * (2.0 * fraction - 1.0)
          )
        if abs(float(target_angle) - expected_angle) > source_band.invariant_tolerance * max(
          1.0,
          abs(float(target_angle)),
          abs(expected_angle),
        ):
          envelope_verified = False
          break

  if (
    source_band is not None
    and shock is not None
    and len(shock.shock_points_m) == len(shock.upstream_states)
    and len(shock.shock_points_m) == len(shock.upstream_pressure_Pa)
  ):
    upstream_coupling_verified = True
    for point, state, pressure in zip(
      shock.shock_points_m,
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      strict=True,
    ):
      sampled_state = source_band.state_at(
        point,
        position_tolerance_m=source_sampling_position_tolerance,
      )
      sampled_pressure = source_band.static_pressure_at(
        point,
        position_tolerance_m=source_sampling_position_tolerance,
      )
      upstream_coupling_verified = upstream_coupling_verified and bool(
        _caustic_state_matches(
          sampled_state,
          state,
          position_tolerance_m=source_sampling_position_tolerance,
          state_tolerance=source_band.invariant_tolerance,
        )
        and _pressure_matches(
          sampled_pressure,
          pressure,
          pressure_tolerance=source_band.pressure_tolerance,
        )
      )

  shock_curve_verified = bool(
    shock is not None
    and shock.converged
    and shock.shock_fit is not None
    and shock.shock_fit.converged
    and len(shock.shock_points_m) >= 3
  )
  if field_result is not None and physical_field is not None:
    expected_incoming_states = tuple(
      sample.state for sample in result.incoming_handoff
    )
    expected_incoming_pressures = tuple(
      sample.total_pressure_Pa for sample in result.incoming_handoff
    )
    incoming_handoff_verified = bool(
      physical_field.incoming_handoff_states == expected_incoming_states
      and physical_field.incoming_handoff_total_pressure_Pa
      == expected_incoming_pressures
    )
  physical_field_verified = bool(
    field_measurement is not None and field_measurement.converged
  )
  state_sampling_verified = bool(
    field_measurement is not None
    and field_measurement.field_state_sampling_verified == (True,)
  )
  bounded_physical_field_verified = bool(
    source_field_verified
    and attachment_point_verified
    and attachment_pressure_verified
    and zero_strength_attachment_verified
    and envelope_verified
    and shock_curve_verified
    and physical_field_verified
    and state_sampling_verified
    and upstream_coupling_verified
    and incoming_handoff_verified
  )

  if not source_field_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.SOURCE_FAILURE
    message = 'alternating source band failed its independent measurement'
  elif not attachment_point_verified or not attachment_pressure_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.SHOCK_FAILURE
    message = 'shock attachment did not reproduce the independent source-band seam'
  elif not zero_strength_attachment_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.SHOCK_FAILURE
    message = 'shock attachment did not retain the explicit zero-strength ambient seam'
  elif not envelope_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.ENVELOPE_FAILURE
    message = 'shock downstream angles do not reproduce the stored local compression envelope'
  elif not shock_curve_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.SHOCK_FAILURE
    message = 'shock curve did not pass the independent attached-shock seam checks'
  elif not physical_field_verified or not state_sampling_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.FIELD_FAILURE
    message = 'ambient-closed physical field failed its independent raw-field measurement'
  elif not upstream_coupling_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.FIELD_FAILURE
    message = 'physical shock field did not preserve the bounded alternating upstream samples'
  elif not incoming_handoff_verified:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.FIELD_FAILURE
    message = 'physical shock field did not retain the exact incoming chain handoff'
  else:
    status = MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.CONVERGED
    message = (
      'alternating source band, zero-strength attachment, compression envelope, '
      'shock curve, ambient-closed field, and upstream coupling passed independent '
      'measurement; canonical free-boundary validation and promotion remain pending'
    )
  measurement = _reflected_domain_alternating_physical_field_measurement_failure(
    status,
    solver_status=solver_status,
    source_measurement=source_measurement,
    field_measurement=field_measurement,
    source_field_verified=source_field_verified,
    attachment_point_verified=attachment_point_verified,
    attachment_pressure_verified=attachment_pressure_verified,
    zero_strength_attachment_verified=zero_strength_attachment_verified,
    envelope_verified=envelope_verified,
    shock_curve_verified=shock_curve_verified,
    physical_field_verified=physical_field_verified,
    state_sampling_verified=state_sampling_verified,
    upstream_coupling_verified=upstream_coupling_verified,
    incoming_handoff_verified=incoming_handoff_verified,
    bounded_physical_field_verified=bounded_physical_field_verified,
    compression_amplitude_rad=result.compression_amplitude_rad,
    shock_sample_count=shock_sample_count,
    message=message,
  )
  if bounded_physical_field_verified:
    object.__setattr__(measurement, 'physical_closure_verified', True)
  return measurement
####


def _reflected_domain_solver_owned_first_cell_measurement_failure(
  status: MocReflectedDomainSolverOwnedFirstCellMeasurementStatus,
  message: str,
  *,
  solver_status: str | None = None,
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None = None,
  trial_count: int = 0,
  target_centerline_verified: bool = False,
  amplitude_bracket_verified: bool = False,
  trial_amplitudes_verified: bool = False,
  trial_residuals_verified: bool = False,
  selected_trial_verified: bool = False,
  selected_field_measurement: (
    MocReflectedDomainAlternatingPhysicalFieldMeasurement | None
  ) = None,
  selected_field_verified: bool = False,
  scalar_endpoint_verified: bool = False,
  physical_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  selected_amplitude: float | None = None,
  selected_residual_m: float | None = None,
  minimum_absolute_residual_m: float | None = None,
) -> MocReflectedDomainSolverOwnedFirstCellMeasurement:
  return MocReflectedDomainSolverOwnedFirstCellMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_SOLVER_OWNED_FIRST_CELL_OPERATOR_ID,
    solver_status=solver_status,
    source_measurement=source_measurement,
    trial_count=trial_count,
    target_centerline_verified=target_centerline_verified,
    amplitude_bracket_verified=amplitude_bracket_verified,
    trial_amplitudes_verified=trial_amplitudes_verified,
    trial_residuals_verified=trial_residuals_verified,
    selected_trial_verified=selected_trial_verified,
    selected_field_measurement=selected_field_measurement,
    selected_field_verified=selected_field_verified,
    scalar_endpoint_verified=scalar_endpoint_verified,
    physical_closure_verified=physical_closure_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_isolation_verified=fidelity_isolation_verified,
    selected_amplitude=selected_amplitude,
    selected_residual_m=selected_residual_m,
    minimum_absolute_residual_m=minimum_absolute_residual_m,
    message=message,
  )
####


def measure_moc_reflected_domain_solver_owned_first_cell(
  result: MocReflectedDomainSolverOwnedFirstCellResult,
  *,
  endpoint_tolerance_m: float = 1.0e-6,
  position_tolerance_m: float = 1.0e-8,
) -> MocReflectedDomainSolverOwnedFirstCellMeasurement:
  """Independently audit a solver-owned first-cell endpoint iteration.

  The operator recomputes source-band evidence, remeasures every retained
  physical trial, and derives each endpoint residual from the raw shock field.
  It recognizes a reproducible no-bracket result as a successful research
  audit, while only a measured root can satisfy the scalar endpoint gate.
  Neither outcome closes the canonical reflected free boundary or authorizes
  chain promotion.
  """

  for name, value in (
    ('endpoint_tolerance_m', endpoint_tolerance_m),
    ('position_tolerance_m', position_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not isinstance(
    result,
    MocReflectedDomainSolverOwnedFirstCellResult,
  ):
    return _reflected_domain_solver_owned_first_cell_measurement_failure(
      MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.INVALID_INPUT,
      'result must be a MocReflectedDomainSolverOwnedFirstCellResult',
    )

  endpoint_tolerance = float(endpoint_tolerance_m)
  position_tolerance = float(position_tolerance_m)
  solver_status = getattr(result.status, 'value', str(result.status))
  source_band = result.source_band
  source_measurement = (
    None
    if source_band is None
    else measure_moc_reflected_domain_alternating_source(source_band)
  )
  source_verified = bool(
    source_measurement is not None and source_measurement.converged
  )
  trial_count = len(result.trials)

  target_centerline_verified = False
  if (
    source_band is not None
    and isinstance(result.outer_source_index, int)
    and not isinstance(result.outer_source_index, bool)
    and 0 <= result.outer_source_index < len(source_band.outer_source_states)
    and isinstance(result.target_centerline_index, int)
    and not isinstance(result.target_centerline_index, bool)
    and 0 <= result.target_centerline_index
    < len(source_band.centerline_source_states)
    and result.target_centerline_point_m is not None
  ):
    target_state = source_band.centerline_source_states[
      result.target_centerline_index
    ]
    outer_state = source_band.outer_source_states[result.outer_source_index]
    target_centerline_verified = bool(
      _caustic_points_match(
        (result.target_centerline_point_m,),
        ((target_state.x_m, target_state.y_m),),
        position_tolerance_m=position_tolerance,
      )
      and abs(target_state.y_m - source_band.target_centerline_y_m)
      <= position_tolerance
      and target_state.x_m > outer_state.x_m + position_tolerance
    )

  amplitude_bracket_verified = False
  bracket = result.compression_amplitude_bracket
  if bracket is not None and len(bracket) == 2:
    lower, upper = (float(bracket[0]), float(bracket[1]))
    amplitude_bracket_verified = bool(
      isfinite(lower)
      and isfinite(upper)
      and lower > 0.0
      and upper > lower
    )

  def amplitude_matches(first: float, second: float) -> bool:
    return abs(first - second) <= 1.0e-12 * max(1.0, abs(first), abs(second))

  trial_amplitudes_verified = bool(
    amplitude_bracket_verified
    and trial_count >= 2
    and bracket is not None
    and amplitude_matches(result.trials[0].compression_amplitude_rad, bracket[0])
    and amplitude_matches(result.trials[1].compression_amplitude_rad, bracket[1])
    and all(
      bracket[0] <= trial.compression_amplitude_rad <= bracket[1]
      for trial in result.trials
    )
    and len({trial.compression_amplitude_rad for trial in result.trials})
    == trial_count
  )

  trial_residuals_verified = bool(
    target_centerline_verified and trial_count > 0
  )
  if source_band is not None and result.target_centerline_point_m is not None:
    target_x = result.target_centerline_point_m[0]
    source_fingerprint = _alternating_source_geometry_fingerprint(source_band)
    for trial in result.trials:
      physical_field = trial.physical_field
      if physical_field is None:
        trial_residuals_verified = trial_residuals_verified and bool(
          trial.endpoint_m is None and trial.residual_m is None
        )
        continue
      trial_measurement = measure_moc_reflected_domain_alternating_physical_field(
        physical_field
      )
      trial_source_verified = bool(
        physical_field.source_band is not None
        and _alternating_source_geometry_fingerprint(
          physical_field.source_band
        )
        == source_fingerprint
      )
      raw_field = physical_field.field
      if raw_field is None or not raw_field.shock_boundary_points_m:
        trial_residuals_verified = trial_residuals_verified and bool(
          trial.endpoint_m is None and trial.residual_m is None
        )
        continue
      trial_profile_verified = bool(
        abs(
          physical_field.compression_envelope_skew
          - result.compression_envelope_skew
        )
        <= 1.0e-12
      )
      expected_endpoint = raw_field.shock_boundary_points_m[-1]
      expected_residual = expected_endpoint[0] - target_x
      trial_residuals_verified = trial_residuals_verified and bool(
        trial_source_verified
        and trial_profile_verified
        and trial_measurement.converged
        and trial.endpoint_m is not None
        and trial.residual_m is not None
        and hypot(
          trial.endpoint_m[0] - expected_endpoint[0],
          trial.endpoint_m[1] - expected_endpoint[1],
        )
        <= endpoint_tolerance
        and abs(trial.residual_m - expected_residual) <= endpoint_tolerance
      )
  else:
    trial_residuals_verified = False

  selected_trial_verified = False
  selected_field_measurement = None
  selected_field_verified = False
  selected_trial = None
  if (
    isinstance(result.selected_trial_index, int)
    and not isinstance(result.selected_trial_index, bool)
    and 0 <= result.selected_trial_index < trial_count
  ):
    selected_trial = result.trials[result.selected_trial_index]
    selected_trial_verified = bool(
      result.selected_physical_field is selected_trial.physical_field
      and result.selected_compression_amplitude_rad is not None
      and amplitude_matches(
        result.selected_compression_amplitude_rad,
        selected_trial.compression_amplitude_rad,
      )
      and (
        (result.closure_residual_m is None and selected_trial.residual_m is None)
        or (
          result.closure_residual_m is not None
          and selected_trial.residual_m is not None
          and abs(result.closure_residual_m - selected_trial.residual_m)
          <= endpoint_tolerance
        )
      )
    )
    if result.selected_physical_field is not None:
      selected_field_measurement = (
        measure_moc_reflected_domain_alternating_physical_field(
          result.selected_physical_field
        )
      )
      selected_field_verified = bool(
        selected_trial_verified
        and selected_field_measurement.converged
        and abs(
          result.selected_physical_field.compression_envelope_skew
          - result.compression_envelope_skew
        )
        <= 1.0e-12
        and source_band is not None
        and result.selected_physical_field.source_band is not None
        and _alternating_source_geometry_fingerprint(
          result.selected_physical_field.source_band
        )
        == _alternating_source_geometry_fingerprint(source_band)
      )

  residuals = tuple(
    trial.residual_m
    for trial in result.trials
    if trial.residual_m is not None and isfinite(trial.residual_m)
  )
  minimum_absolute_residual = (
    None if not residuals else min(abs(value) for value in residuals)
  )
  scalar_endpoint_verified = bool(
    result.status is MocReflectedDomainSolverOwnedFirstCellStatus.CONVERGED_CENTERLINE_ENDPOINT
    and selected_field_verified
    and result.closure_residual_m is not None
    and abs(result.closure_residual_m) <= endpoint_tolerance
  )
  no_bracket_outcome_verified = bool(
    result.status
    is MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE
    and selected_field_verified
    and trial_residuals_verified
    and len(residuals) >= 2
    and all(abs(value) > endpoint_tolerance for value in residuals)
    and (
      all(value > 0.0 for value in residuals)
      or all(value < 0.0 for value in residuals)
    )
  )
  physical_closure_verified = bool(
    source_verified
    and target_centerline_verified
    and trial_amplitudes_verified
    and trial_residuals_verified
    and scalar_endpoint_verified
    and selected_field_verified
  )
  fidelity_isolation_verified = bool(
    not result.canonical_free_boundary_verified
    and not result.canonical_euler_verified
    and not result.external_validation_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and (
      selected_field_measurement is None
      or selected_field_measurement.chain_promotion_blocked
    )
  )

  if not source_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.SOURCE_FAILURE
    message = 'alternating source band failed independent measurement'
  elif not target_centerline_verified or not amplitude_bracket_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CLOSURE_FAILURE
    message = 'solver-owned centerline target or amplitude bracket failed measurement'
  elif not trial_amplitudes_verified or not trial_residuals_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.TRIAL_FAILURE
    message = 'one or more retained endpoint trials failed independent measurement'
  elif not selected_trial_verified or not selected_field_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.TRIAL_FAILURE
    message = 'selected endpoint trial failed independent physical-field measurement'
  elif scalar_endpoint_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CONVERGED
    message = (
      'solver-owned endpoint root and all retained local physical trials passed '
      'independent measurement; canonical free-boundary validation remains pending'
    )
  elif no_bracket_outcome_verified:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CONVERGED
    message = (
      'solver-owned endpoint bracket and retained no-root residuals passed '
      'independent measurement; local field remains a non-promotable research '
      'reference'
    )
  else:
    status = MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CLOSURE_FAILURE
    message = 'solver-owned endpoint outcome failed independent closure measurement'

  return _reflected_domain_solver_owned_first_cell_measurement_failure(
    status,
    message,
    solver_status=solver_status,
    source_measurement=source_measurement,
    trial_count=trial_count,
    target_centerline_verified=target_centerline_verified,
    amplitude_bracket_verified=amplitude_bracket_verified,
    trial_amplitudes_verified=trial_amplitudes_verified,
    trial_residuals_verified=trial_residuals_verified,
    selected_trial_verified=selected_trial_verified,
    selected_field_measurement=selected_field_measurement,
    selected_field_verified=selected_field_verified,
    scalar_endpoint_verified=scalar_endpoint_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    selected_amplitude=result.selected_compression_amplitude_rad,
    selected_residual_m=result.closure_residual_m,
    minimum_absolute_residual_m=minimum_absolute_residual,
  )
####


def _reflected_domain_global_shock_remesh_measurement_failure(
  status: MocReflectedDomainGlobalShockRemeshMeasurementStatus,
  message: str,
  *,
  solver_status: str | None = None,
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None = None,
  attempt_count: int = 0,
  attempt_measurements: Sequence[
    MocReflectedDomainSolverOwnedFirstCellMeasurement
  ] = (),
  source_field_verified: bool = False,
  attempt_identity_verified: bool = False,
  attempt_shape_verified: bool = False,
  attempt_residuals_verified: bool = False,
  selected_attempt_verified: bool = False,
  global_endpoint_verified: bool = False,
  no_endpoint_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  selected_residual_m: float | None = None,
  endpoint_tolerance_m: float = 1.0e-6,
) -> MocReflectedDomainGlobalShockRemeshMeasurement:
  return MocReflectedDomainGlobalShockRemeshMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_GLOBAL_SHOCK_REMESH_OPERATOR_ID,
    solver_status=solver_status,
    source_measurement=source_measurement,
    attempt_count=attempt_count,
    attempt_measurements=tuple(attempt_measurements),
    source_field_verified=source_field_verified,
    attempt_identity_verified=attempt_identity_verified,
    attempt_shape_verified=attempt_shape_verified,
    attempt_residuals_verified=attempt_residuals_verified,
    selected_attempt_verified=selected_attempt_verified,
    global_endpoint_verified=global_endpoint_verified,
    no_endpoint_closure_verified=no_endpoint_closure_verified,
    physical_closure_verified=False,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_isolation_verified=fidelity_isolation_verified,
    selected_residual_m=selected_residual_m,
    endpoint_tolerance_m=endpoint_tolerance_m,
    message=message,
  )
####


def measure_moc_reflected_domain_global_shock_remesh(
  result: MocReflectedDomainGlobalShockRemeshResult,
  *,
  endpoint_tolerance_m: float = 1.0e-6,
) -> MocReflectedDomainGlobalShockRemeshMeasurement:
  """Independently audit every attempt in a global shock remesh sweep.

  The sweep is accepted as a research measurement when all retained attempts
  can be remeasured and the declared no-root outcome is reproduced.  This is
  deliberately stricter than accepting the aggregate solver status: a
  changed source pair, profile skew, selected residual, or trial field must
  invalidate the audit.  No outcome from this operator closes the canonical
  reflected free-boundary/Euler problem.
  """

  if not isfinite(float(endpoint_tolerance_m)) or float(endpoint_tolerance_m) <= 0.0:
    raise ValueError('endpoint_tolerance_m must be finite and positive')
  endpoint_tolerance = float(endpoint_tolerance_m)
  if not isinstance(result, MocReflectedDomainGlobalShockRemeshResult):
    return _reflected_domain_global_shock_remesh_measurement_failure(
      MocReflectedDomainGlobalShockRemeshMeasurementStatus.INVALID_INPUT,
      'result must be a MocReflectedDomainGlobalShockRemeshResult',
      endpoint_tolerance_m=endpoint_tolerance,
    )

  solver_status = getattr(result.status, 'value', str(result.status))
  source_band = result.source_band
  source_measurement = (
    None
    if source_band is None
    else measure_moc_reflected_domain_alternating_source(source_band)
  )
  source_field_verified = bool(
    source_measurement is not None and source_measurement.converged
  )
  attempts = tuple(result.attempts)
  attempt_measurements = tuple(
    measure_moc_reflected_domain_solver_owned_first_cell(
      attempt.first_cell_result,
      endpoint_tolerance_m=endpoint_tolerance,
    )
    for attempt in attempts
  )
  attempt_count = len(attempts)

  attempt_identity_verified = bool(attempt_count > 0)
  expected_source_fingerprint = (
    None
    if source_band is None
    else _alternating_source_geometry_fingerprint(source_band)
  )
  for attempt in attempts:
    first = attempt.first_cell_result
    first_source_fingerprint = (
      None
      if first.source_band is None
      else _alternating_source_geometry_fingerprint(first.source_band)
    )
    selected_field = first.selected_physical_field
    selected_profile_verified = bool(
      selected_field is not None
      and abs(
        selected_field.compression_envelope_skew
        - attempt.compression_envelope_skew
      )
      <= 1.0e-12
    )
    attempt_identity_verified = attempt_identity_verified and bool(
      first.outer_source_index == attempt.outer_source_index
      and first.target_centerline_index == attempt.target_centerline_index
      and abs(
        first.compression_envelope_skew
        - attempt.compression_envelope_skew
      )
      <= 1.0e-12
      and first_source_fingerprint == expected_source_fingerprint
      and selected_profile_verified
    )

  attempt_shape_verified = bool(
    attempt_count > 0
    and len(attempt_measurements) == attempt_count
    and all(
      measurement.converged
      and measurement.selected_field_verified
      and measurement.trial_residuals_verified
      for measurement in attempt_measurements
    )
  )

  attempt_residuals_verified = bool(attempt_count > 0)
  residuals: list[float] = []
  for attempt, measurement in zip(
    attempts,
    attempt_measurements,
    strict=True,
  ):
    first = attempt.first_cell_result
    selected_residual = measurement.selected_residual_m
    if selected_residual is not None and isfinite(selected_residual):
      residuals.append(float(selected_residual))
    attempt_residuals_verified = attempt_residuals_verified and bool(
      measurement.trial_residuals_verified
      and measurement.selected_field_verified
      and first.closure_residual_m is not None
      and selected_residual is not None
      and attempt.residual_m is not None
      and abs(first.closure_residual_m - selected_residual)
      <= endpoint_tolerance
      and abs(attempt.residual_m - selected_residual) <= endpoint_tolerance
    )

  selected_attempt_verified = False
  selected_measurement = None
  selected_attempt = result.selected_attempt
  if (
    selected_attempt is not None
    and isinstance(result.selected_attempt_index, int)
    and not isinstance(result.selected_attempt_index, bool)
    and 0 <= result.selected_attempt_index < attempt_count
  ):
    selected_measurement = attempt_measurements[result.selected_attempt_index]
    valid_residuals = tuple(
      measurement.selected_residual_m
      for measurement in attempt_measurements
      if measurement.selected_field_verified
      and measurement.selected_residual_m is not None
      and isfinite(measurement.selected_residual_m)
    )
    selected_attempt_verified = bool(
      result.attempts[result.selected_attempt_index] is selected_attempt
      and selected_measurement.converged
      and selected_measurement.selected_field_verified
      and result.selected_residual_m is not None
      and selected_attempt.residual_m is not None
      and abs(
        result.selected_residual_m - selected_attempt.residual_m
      ) <= endpoint_tolerance
      and valid_residuals
      and abs(result.selected_residual_m)
      <= min(abs(value) for value in valid_residuals) + endpoint_tolerance
    )

  global_endpoint_verified = bool(
    result.status is MocReflectedDomainGlobalShockRemeshStatus.CONVERGED_ENDPOINT
    and selected_attempt_verified
    and selected_attempt is not None
    and selected_attempt.converged
    and selected_measurement is not None
    and selected_measurement.scalar_endpoint_verified
    and result.selected_residual_m is not None
    and abs(result.selected_residual_m) <= endpoint_tolerance
  )
  no_endpoint_closure_verified = bool(
    result.status
    is MocReflectedDomainGlobalShockRemeshStatus.NO_ENDPOINT_CLOSURE
    and attempt_shape_verified
    and attempt_residuals_verified
    and selected_attempt_verified
    and all(not attempt.converged for attempt in attempts)
    and all(
      not measurement.scalar_endpoint_verified
      and measurement.selected_residual_m is not None
      and abs(measurement.selected_residual_m) > endpoint_tolerance
      for measurement in attempt_measurements
    )
  )
  fidelity_isolation_verified = bool(
    not result.canonical_free_boundary_verified
    and not result.canonical_euler_verified
    and not result.external_validation_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and all(
      measurement.fidelity_isolation_verified
      for measurement in attempt_measurements
    )
  )

  if result.status is MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.INVALID_INPUT
    message = 'global reflected-shock remesh input rejection was independently recorded'
  elif not source_field_verified:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.SOURCE_FAILURE
    message = 'global reflected-shock remesh source band failed independent measurement'
  elif not attempt_identity_verified or not attempt_shape_verified:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
    message = 'one or more global remesh attempts failed independent identity or field measurement'
  elif not attempt_residuals_verified or not selected_attempt_verified:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
    message = 'global remesh attempt residuals or selected-attempt lineage failed independent measurement'
  elif global_endpoint_verified or no_endpoint_closure_verified:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.CONVERGED
    message = (
      'global reflected-shock remesh attempts, source/profile lineage, and '
      'endpoint outcome passed independent measurement; canonical reflected '
      'free-boundary validation remains pending'
    )
  else:
    status = MocReflectedDomainGlobalShockRemeshMeasurementStatus.CLOSURE_FAILURE
    message = 'global reflected-shock remesh outcome failed independent closure measurement'

  return _reflected_domain_global_shock_remesh_measurement_failure(
    status,
    message,
    solver_status=solver_status,
    source_measurement=source_measurement,
    attempt_count=attempt_count,
    attempt_measurements=attempt_measurements,
    source_field_verified=source_field_verified,
    attempt_identity_verified=attempt_identity_verified,
    attempt_shape_verified=attempt_shape_verified,
    attempt_residuals_verified=attempt_residuals_verified,
    selected_attempt_verified=selected_attempt_verified,
    global_endpoint_verified=global_endpoint_verified,
    no_endpoint_closure_verified=no_endpoint_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    selected_residual_m=result.selected_residual_m,
    endpoint_tolerance_m=endpoint_tolerance,
  )
####


class MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus(str, Enum):
  """Outcome of independently auditing a globally coupled Euler field."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'source_failure'
  ATTEMPT_FAILURE = 'attempt_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  FRONTIER_FAILURE = 'frontier_failure'
  FIELD_FAILURE = 'field_failure'
  FLAG_FAILURE = 'flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryMeasurement:
  """Independent evidence for the bounded global Euler shock bridge.

  The operator rechecks source-band membership, selected-attempt lineage,
  endpoint Mach-wave tangents, the retained ambient boundary, and the
  conservative Euler audit of the assembled field.  It never calls the
  global closure solver and never changes its fidelity or promotion flags.
  """

  status: MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus
  operator_id: str
  solver_status: str | None
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None
  field_euler_measurement: Any | None
  source_field_verified: bool
  selected_attempt_verified: bool
  initial_geometry_verified: bool
  remeshed_geometry_verified: bool
  source_frontier_verified: bool
  endpoint_tangents_verified: bool
  upstream_sampling_verified: bool
  incoming_handoff_verified: bool
  shock_boundary_verified: bool
  ambient_boundary_verified: bool
  physical_field_verified: bool
  physical_closure_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  external_validation_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_isolation_verified: bool
  shock_sample_count: int
  field_cell_count: int
  source_frontier_x_m: float | None = None
  first_endpoint_tangent_residual_rad: float | None = None
  last_endpoint_tangent_residual_rad: float | None = None
  maximum_shock_jump_mass_residual: float | None = None
  maximum_shock_jump_momentum_residual: float | None = None
  maximum_shock_jump_energy_residual: float | None = None
  maximum_cell_euler_residual: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus'
      )
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    for name in ('shock_sample_count', 'field_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    for name in (
      'source_field_verified',
      'selected_attempt_verified',
      'initial_geometry_verified',
      'remeshed_geometry_verified',
      'source_frontier_verified',
      'endpoint_tangents_verified',
      'upstream_sampling_verified',
      'incoming_handoff_verified',
      'shock_boundary_verified',
      'ambient_boundary_verified',
      'physical_field_verified',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in (
      'source_frontier_x_m',
      'first_endpoint_tangent_residual_rad',
      'last_endpoint_tangent_residual_rad',
      'maximum_shock_jump_mass_residual',
      'maximum_shock_jump_momentum_residual',
      'maximum_shock_jump_energy_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or (
          name != 'source_frontier_x_m' and numeric < 0.0
        ):
          raise ValueError(f'{name} must be finite and valid when supplied')
        object.__setattr__(self, name, numeric)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.CONVERGED
    )
  ####

  @property
  def local_euler_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock_boundary_verified
      and self.physical_field_verified
      and self.field_euler_measurement is not None
      and self.field_euler_measurement.local_euler_consistency_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    field_measurement_report = None
    if self.field_euler_measurement is not None:
      field_measurement_report = self.field_euler_measurement.as_report()
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'converged': self.converged,
      'local_euler_consistency_verified': self.local_euler_consistency_verified,
      'source_measurement': (
        None
        if self.source_measurement is None
        else self.source_measurement.as_report()
      ),
      'field_euler_measurement': field_measurement_report,
      'shock_sample_count': self.shock_sample_count,
      'field_cell_count': self.field_cell_count,
      'source_frontier_x_m': self.source_frontier_x_m,
      'first_endpoint_tangent_residual_rad': (
        self.first_endpoint_tangent_residual_rad
      ),
      'last_endpoint_tangent_residual_rad': (
        self.last_endpoint_tangent_residual_rad
      ),
      'maximum_shock_jump_mass_residual': (
        self.maximum_shock_jump_mass_residual
      ),
      'maximum_shock_jump_momentum_residual': (
        self.maximum_shock_jump_momentum_residual
      ),
      'maximum_shock_jump_energy_residual': (
        self.maximum_shock_jump_energy_residual
      ),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'source_field_verified': self.source_field_verified,
        'selected_attempt_verified': self.selected_attempt_verified,
        'initial_geometry_verified': self.initial_geometry_verified,
        'remeshed_geometry_verified': self.remeshed_geometry_verified,
        'source_frontier_verified': self.source_frontier_verified,
        'endpoint_tangents_verified': self.endpoint_tangents_verified,
        'upstream_sampling_verified': self.upstream_sampling_verified,
        'incoming_handoff_verified': self.incoming_handoff_verified,
        'shock_boundary_verified': self.shock_boundary_verified,
        'ambient_boundary_verified': self.ambient_boundary_verified,
        'physical_field_verified': self.physical_field_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'claim_status': (
        'independent-global-euler-shock-boundary-audit; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####


def _reflected_domain_global_euler_shock_boundary_measurement_failure(
  status: MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus,
  message: str,
  *,
  solver_status: str | None = None,
  source_measurement: MocReflectedDomainAlternatingSourceMeasurement | None = None,
  field_euler_measurement: Any | None = None,
  source_field_verified: bool = False,
  selected_attempt_verified: bool = False,
  initial_geometry_verified: bool = False,
  remeshed_geometry_verified: bool = False,
  source_frontier_verified: bool = False,
  endpoint_tangents_verified: bool = False,
  upstream_sampling_verified: bool = False,
  incoming_handoff_verified: bool = False,
  shock_boundary_verified: bool = False,
  ambient_boundary_verified: bool = False,
  physical_field_verified: bool = False,
  physical_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  shock_sample_count: int = 0,
  field_cell_count: int = 0,
  source_frontier_x_m: float | None = None,
  first_endpoint_tangent_residual_rad: float | None = None,
  last_endpoint_tangent_residual_rad: float | None = None,
  maximum_shock_jump_mass_residual: float | None = None,
  maximum_shock_jump_momentum_residual: float | None = None,
  maximum_shock_jump_energy_residual: float | None = None,
  maximum_cell_euler_residual: float | None = None,
) -> MocReflectedDomainGlobalEulerShockBoundaryMeasurement:
  return MocReflectedDomainGlobalEulerShockBoundaryMeasurement(
    status=status,
    operator_id=MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_OPERATOR_ID,
    solver_status=solver_status,
    source_measurement=source_measurement,
    field_euler_measurement=field_euler_measurement,
    source_field_verified=source_field_verified,
    selected_attempt_verified=selected_attempt_verified,
    initial_geometry_verified=initial_geometry_verified,
    remeshed_geometry_verified=remeshed_geometry_verified,
    source_frontier_verified=source_frontier_verified,
    endpoint_tangents_verified=endpoint_tangents_verified,
    upstream_sampling_verified=upstream_sampling_verified,
    incoming_handoff_verified=incoming_handoff_verified,
    shock_boundary_verified=shock_boundary_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    physical_field_verified=physical_field_verified,
    physical_closure_verified=physical_closure_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_isolation_verified=fidelity_isolation_verified,
    shock_sample_count=shock_sample_count,
    field_cell_count=field_cell_count,
    source_frontier_x_m=source_frontier_x_m,
    first_endpoint_tangent_residual_rad=first_endpoint_tangent_residual_rad,
    last_endpoint_tangent_residual_rad=last_endpoint_tangent_residual_rad,
    maximum_shock_jump_mass_residual=maximum_shock_jump_mass_residual,
    maximum_shock_jump_momentum_residual=maximum_shock_jump_momentum_residual,
    maximum_shock_jump_energy_residual=maximum_shock_jump_energy_residual,
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    message=message,
  )
####


def measure_moc_reflected_domain_global_euler_shock_boundary(
  result: MocReflectedDomainGlobalEulerShockBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocReflectedDomainGlobalEulerShockBoundaryMeasurement:
  """Independently audit the global exact-Euler shock-field bridge.

  This operator checks only retained source/geometry/field data.  It does not
  rerun the closure solve, and a passing result remains below refinement,
  canonical reflected-free-boundary, and external-validation promotion gates.
  """

  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    tangent_tolerance_value = float(tangent_tolerance)
  except (TypeError, ValueError):
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.INVALID_INPUT,
      'global Euler shock-boundary measurement tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      invariant_tolerance_value,
      pressure_tolerance_value,
      tangent_tolerance_value,
    )
  ):
    raise ValueError(
      'global Euler shock-boundary measurement tolerances must be finite and positive'
    )
  if not isinstance(result, MocReflectedDomainGlobalEulerShockBoundaryResult):
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.INVALID_INPUT,
      'result must be a MocReflectedDomainGlobalEulerShockBoundaryResult',
    )

  solver_status = result.status.value
  global_remesh = result.global_remesh
  source_band = None if global_remesh is None else global_remesh.source_band
  source_measurement = (
    None
    if source_band is None
    else measure_moc_reflected_domain_alternating_source(source_band)
  )
  source_field_verified = bool(
    source_measurement is not None and source_measurement.converged
  )
  if not source_field_verified:
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.SOURCE_FAILURE,
      'global Euler shock-boundary source band failed independent measurement',
      solver_status=solver_status,
      source_measurement=source_measurement,
      source_field_verified=False,
    )
  if source_band is None or global_remesh is None:
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.SOURCE_FAILURE,
      'global Euler shock-boundary result did not retain a source band',
      solver_status=solver_status,
      source_measurement=source_measurement,
      source_field_verified=True,
    )

  selected_index = result.selected_attempt_index
  selected_attempt = None
  if (
    isinstance(selected_index, int)
    and not isinstance(selected_index, bool)
    and 0 <= selected_index < len(global_remesh.attempts)
  ):
    selected_attempt = global_remesh.attempts[selected_index]
  selected_attempt_verified = bool(
    selected_attempt is not None
    and result.selected_attempt_index == selected_index
    and result.outer_source_index == selected_attempt.outer_source_index
    and result.target_centerline_index == selected_attempt.target_centerline_index
    and global_remesh.attempts[selected_index] is selected_attempt
  )
  if not selected_attempt_verified or selected_attempt is None:
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.ATTEMPT_FAILURE,
      'global Euler shock-boundary selected-attempt lineage failed measurement',
      solver_status=solver_status,
      source_measurement=source_measurement,
      source_field_verified=True,
    )

  selected_field = selected_attempt.first_cell_result.selected_physical_field
  candidate_field = None if selected_field is None else selected_field.field
  candidate_points = () if candidate_field is None else tuple(
    candidate_field.shock_boundary_points_m
  )
  initial_geometry_verified = bool(
    candidate_field is not None
    and _caustic_points_match(
      result.initial_shock_points_m,
      candidate_points,
      position_tolerance_m=position_tolerance,
    )
  )
  points = tuple(result.remeshed_shock_points_m)
  remeshed_geometry_verified = bool(
    len(points) >= 3
    and all(
      len(point) == 2 and all(isfinite(float(value)) for value in point)
      for point in points
    )
    and all(
      second[0] > first[0] + position_tolerance
      and second[1] <= first[1] + position_tolerance
      for first, second in zip(points, points[1:])
    )
  )
  if not initial_geometry_verified or not remeshed_geometry_verified:
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.GEOMETRY_FAILURE,
      'global Euler shock-boundary geometry failed independent measurement',
      solver_status=solver_status,
      source_measurement=source_measurement,
      source_field_verified=True,
      selected_attempt_verified=True,
      initial_geometry_verified=initial_geometry_verified,
      remeshed_geometry_verified=remeshed_geometry_verified,
      shock_sample_count=len(points),
    )

  outer_index = selected_attempt.outer_source_index
  target_index = selected_attempt.target_centerline_index
  if (
    outer_index < 0
    or outer_index >= len(source_band.outer_source_states)
    or target_index < 0
    or target_index >= len(source_band.centerline_source_states)
  ):
    return _reflected_domain_global_euler_shock_boundary_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.SOURCE_FAILURE,
      'global Euler shock-boundary source indices failed independent measurement',
      solver_status=solver_status,
      source_measurement=source_measurement,
      source_field_verified=True,
      selected_attempt_verified=True,
      initial_geometry_verified=True,
      remeshed_geometry_verified=True,
      shock_sample_count=len(points),
    )
  target_y = source_band.target_centerline_y_m
  target_theta = source_band.target_centerline_flow_angle_rad
  centerline_xs = tuple(
    state.x_m for state in source_band.centerline_source_states
  )
  sampled_states = tuple(
    source_band.state_at(point, position_tolerance_m=position_tolerance)
    for point in points
  )
  sampled_pressures = tuple(
    source_band.static_pressure_at(point, position_tolerance_m=position_tolerance)
    for point in points
  )
  source_frontier_state = source_band.state_at(
    points[-1],
    position_tolerance_m=position_tolerance,
  )
  source_frontier_pressure = source_band.total_pressure_at(
    points[-1],
    position_tolerance_m=position_tolerance,
  )
  outer_source = source_band.outer_source_states[outer_index]
  source_frontier_verified = bool(
    result.source_frontier_verified
    and source_frontier_state is not None
    and source_frontier_pressure is not None
    and result.source_frontier_state is not None
    and _caustic_state_matches(
      result.source_frontier_state,
      source_frontier_state,
      position_tolerance_m=position_tolerance,
      state_tolerance=invariant_tolerance_value,
    )
    and _pressure_matches(
      result.source_frontier_total_pressure_Pa,
      source_frontier_pressure,
      pressure_tolerance=pressure_tolerance_value,
    )
    and abs(points[-1][1] - target_y) <= position_tolerance
    and abs(source_frontier_state.y_m - target_y) <= position_tolerance
    and abs(source_frontier_state.theta_rad - target_theta)
    <= invariant_tolerance_value
    and centerline_xs[0] - position_tolerance
    <= points[-1][0]
    <= centerline_xs[-1] + position_tolerance
    and _caustic_state_matches(
      sampled_states[0],
      outer_source,
      position_tolerance_m=position_tolerance,
      state_tolerance=invariant_tolerance_value,
    )
  )
  upstream_sampling_verified = bool(
    all(state is not None for state in sampled_states)
    and all(
      pressure is not None
      and isfinite(float(pressure))
      and pressure > 0.0
      for pressure in sampled_pressures
    )
  )
  curve = result.shock_boundary
  if curve is not None:
    upstream_sampling_verified = upstream_sampling_verified and bool(
      len(curve.upstream_states) == len(points)
      and len(curve.upstream_static_pressure_Pa) == len(points)
      and all(
        _caustic_state_matches(
          actual,
          expected,
          position_tolerance_m=position_tolerance,
          state_tolerance=invariant_tolerance_value,
        )
        and _pressure_matches(
          actual_pressure,
          expected_pressure,
          pressure_tolerance=pressure_tolerance_value,
        )
        for actual, expected, actual_pressure, expected_pressure in zip(
          curve.upstream_states,
          sampled_states,
          curve.upstream_static_pressure_Pa,
          sampled_pressures,
          strict=True,
        )
      )
    )
  else:
    upstream_sampling_verified = False

  endpoint_tangents_verified = False
  first_residual = result.first_endpoint_tangent_residual_rad
  last_residual = result.last_endpoint_tangent_residual_rad
  if sampled_states[0] is not None and source_frontier_state is not None:
    try:
      first_slope = (
        sampled_states[0].theta_rad - sampled_states[0].mu_rad
      )
      last_slope = (
        source_frontier_state.theta_rad - source_frontier_state.mu_rad
      )
      first_actual = (points[1][1] - points[0][1]) / (points[1][0] - points[0][0])
      last_actual = (
        points[-1][1] - points[-2][1]
      ) / (points[-1][0] - points[-2][0])
      first_expected = tan(first_slope)
      last_expected = tan(last_slope)
      endpoint_tangents_verified = bool(
        first_residual is not None
        and last_residual is not None
        and abs(first_actual - first_expected) <= tangent_tolerance_value
        and abs(last_actual - last_expected) <= tangent_tolerance_value
        and abs(first_residual - abs(first_actual - first_expected))
        <= tangent_tolerance_value
        and abs(last_residual - abs(last_actual - last_expected))
        <= tangent_tolerance_value
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError, ZeroDivisionError):
      endpoint_tangents_verified = False

  physical_result = result.physical_field
  physical_field = None if physical_result is None else physical_result.field
  field_euler_measurement = None
  if physical_field is not None:
    try:
      from exhaust_plume.validation.moc_euler import (
        measure_moc_physical_field_euler_audit,
      )

      field_euler_measurement = measure_moc_physical_field_euler_audit(
        physical_field,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      field_euler_measurement = None
  shock_boundary_verified = bool(
    curve is not None
    and curve.converged
    and curve.local_euler_verified
    and curve.zero_strength_endpoints_allowed
    and _caustic_points_match(
      curve.shock_points_m,
      points,
      position_tolerance_m=position_tolerance,
    )
  )
  ambient_boundary_verified = False
  if physical_result is not None and physical_result.ambient_march is not None:
    march = physical_result.ambient_march
    ambient_boundary_verified = bool(
      march.converged
      and march.ambient_boundary.converged
      and len(march.boundary_samples) == len(points)
      and len(march.point_results) == len(points)
      and march.maximum_geometry_residual_m is not None
      and march.maximum_geometry_residual_m <= position_tolerance
      and march.maximum_absolute_pressure_residual is not None
      and march.maximum_absolute_pressure_residual <= pressure_tolerance_value
      and march.maximum_absolute_invariant_residual is not None
      and march.maximum_absolute_invariant_residual <= invariant_tolerance_value
      and march.attachment_relative_pressure_residual is not None
      and abs(march.attachment_relative_pressure_residual)
      <= pressure_tolerance_value
      and all(item.converged for item in march.point_results)
    )
  physical_field_verified = bool(
    physical_result is not None
    and physical_result.converged
    and physical_result.physical_closure_verified
    and physical_field is not None
    and physical_field.state_sampling_available
    and field_euler_measurement is not None
    and field_euler_measurement.converged
    and field_euler_measurement.local_euler_consistency_verified
  )
  incoming_handoff_verified = bool(
    physical_result is not None
    and result.incoming_handoff_verified
    and physical_result.incoming_handoff == source_band.incoming_handoff
  )
  physical_closure_verified = bool(
    result.physical_closure_verified
    and source_frontier_verified
    and endpoint_tangents_verified
    and upstream_sampling_verified
    and incoming_handoff_verified
    and shock_boundary_verified
    and ambient_boundary_verified
    and physical_field_verified
  )
  fidelity_isolation_verified = bool(
    not result.canonical_free_boundary_verified
    and not result.canonical_euler_verified
    and not result.external_validation_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and (curve is None or curve.chain_promotion_blocked)
    and (physical_result is None or physical_result.chain_promotion_blocked)
    and (physical_result is None or not physical_result.production_claim_allowed)
  )
  field_cell_count = 0 if physical_field is None else len(physical_field.cells)
  maximums = (
    None
    if field_euler_measurement is None
    else (
      field_euler_measurement.maximum_shock_jump_mass_residual,
      field_euler_measurement.maximum_shock_jump_momentum_residual,
      field_euler_measurement.maximum_shock_jump_energy_residual,
      field_euler_measurement.maximum_cell_euler_residual,
    )
  )
  common = dict(
    solver_status=solver_status,
    source_measurement=source_measurement,
    field_euler_measurement=field_euler_measurement,
    source_field_verified=source_field_verified,
    selected_attempt_verified=selected_attempt_verified,
    initial_geometry_verified=initial_geometry_verified,
    remeshed_geometry_verified=remeshed_geometry_verified,
    source_frontier_verified=source_frontier_verified,
    endpoint_tangents_verified=endpoint_tangents_verified,
    upstream_sampling_verified=upstream_sampling_verified,
    incoming_handoff_verified=incoming_handoff_verified,
    shock_boundary_verified=shock_boundary_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    physical_field_verified=physical_field_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    shock_sample_count=len(points),
    field_cell_count=field_cell_count,
    source_frontier_x_m=(
      None if source_frontier_state is None else source_frontier_state.x_m
    ),
    first_endpoint_tangent_residual_rad=first_residual,
    last_endpoint_tangent_residual_rad=last_residual,
    maximum_shock_jump_mass_residual=(None if maximums is None else maximums[0]),
    maximum_shock_jump_momentum_residual=(None if maximums is None else maximums[1]),
    maximum_shock_jump_energy_residual=(None if maximums is None else maximums[2]),
    maximum_cell_euler_residual=(None if maximums is None else maximums[3]),
  )
  if not source_frontier_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FRONTIER_FAILURE
    message = 'source centerline frontier seam failed independent measurement'
  elif not endpoint_tangents_verified or not upstream_sampling_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.GEOMETRY_FAILURE
    message = 'source-coupled shock geometry failed independent measurement'
  elif not shock_boundary_verified or not ambient_boundary_verified or not physical_field_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FIELD_FAILURE
    message = 'global exact-Euler field failed independent boundary or cell measurement'
  elif not physical_closure_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FIELD_FAILURE
    message = 'global exact-Euler closure flag or seam evidence failed measurement'
  elif not fidelity_isolation_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FLAG_FAILURE
    message = 'global exact-Euler bridge weakened its fidelity boundary'
  elif result.status is not MocReflectedDomainGlobalEulerShockBoundaryStatus.CONVERGED:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FIELD_FAILURE
    message = 'global exact-Euler bridge status did not report convergence'
  else:
    status = MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.CONVERGED
    message = (
      'source frontier, remeshed shock geometry, ambient boundary, and '
      'independent local Euler field audit passed; canonical and external '
      'promotion gates remain pending'
    )
  return _reflected_domain_global_euler_shock_boundary_measurement_failure(
    status,
    message,
    **common,
  )
####


def _alternating_source_geometry_fingerprint(
  source: MocReflectedDomainAlternatingSourceResult,
) -> str:
  """Fingerprint source geometry and state rows without the incoming handoff."""

  def state_signature(state: CharacteristicState) -> tuple[float, ...]:
    return (
      state.x_m,
      state.y_m,
      state.theta_rad,
      state.mach,
      state.gamma,
    )

  seed_signature = (
    None
    if source.outer_seed_state is None
    else state_signature(source.outer_seed_state)
  )
  payload = (
    tuple(state_signature(state) for state in source.centerline_source_states),
    tuple(state_signature(state) for state in source.outer_source_states),
    source.centerline_total_pressure_Pa,
    source.outer_total_pressure_Pa,
    seed_signature,
    source.outer_seed_total_pressure_Pa,
    source.ambient_pressure_Pa,
    source.target_centerline_y_m,
    source.target_centerline_flow_angle_rad,
    tuple(tuple(cell.vertices_xr_m) for cell in source.cells),
  )
  return sha256(repr(payload).encode('utf-8')).hexdigest()
####


def _alternating_physical_field_chain_measurement_failure(
  status: MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus,
  message: str,
  *,
  field_count: int = 0,
  field_measurements: Sequence[
    MocReflectedDomainAlternatingPhysicalFieldMeasurement
  ] = (),
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None,
  source_geometry_fingerprints: Sequence[str] = (),
  source_geometry_freshness_verified: bool = False,
  handoff_link_count: int = 0,
  handoff_links_verified: bool | None = None,
  fresh_domain_verified: bool = False,
  physical_closure_verified: bool = False,
) -> MocReflectedDomainAlternatingPhysicalFieldChainMeasurement:
  return MocReflectedDomainAlternatingPhysicalFieldChainMeasurement(
    status=status,
    field_count=field_count,
    field_measurements=tuple(field_measurements),
    physical_field_chain_measurement=physical_field_chain_measurement,
    source_geometry_fingerprints=tuple(source_geometry_fingerprints),
    source_geometry_freshness_verified=source_geometry_freshness_verified,
    handoff_link_count=handoff_link_count,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=fresh_domain_verified,
    physical_closure_verified=physical_closure_verified,
    message=message,
  )
####


def measure_moc_reflected_domain_alternating_physical_field_chain(
  results: Sequence[MocReflectedDomainAlternatingPhysicalFieldResult],
  *,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocReflectedDomainAlternatingPhysicalFieldChainMeasurement:
  """Independently audit a continued alternating-source physical chain.

  Each item is first measured as a source-band/physical-field result.  The
  retained physical fields are then audited together for exact centerline
  handoff and strictly fresh downstream domains.  Source geometry fingerprints
  are compared without including the incoming handoff, so a copied source
  band cannot pass by wrapping it in a new result.  The result is still
  research-only and does not close the canonical reflected free boundary.
  """

  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('area_tolerance_m2', area_tolerance_m2),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    items = tuple(results)
  except TypeError:
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      'results must be an iterable of alternating physical-field results',
    )
  if not items:
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      'at least one alternating physical-field result is required',
    )
  if any(
    not isinstance(item, MocReflectedDomainAlternatingPhysicalFieldResult)
    for item in items
  ):
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      'results must contain only MocReflectedDomainAlternatingPhysicalFieldResult values',
      field_count=len(items),
    )

  measurements = tuple(
    measure_moc_reflected_domain_alternating_physical_field(item)
    for item in items
  )
  source_fingerprints = tuple(
    _alternating_source_geometry_fingerprint(item.source_band)
    if item.source_band is not None
    else 'unavailable'
    for item in items
  )
  source_geometry_freshness_verified = bool(
    all(item.source_band is not None for item in items)
    and all(fingerprint != 'unavailable' for fingerprint in source_fingerprints)
    and len(set(source_fingerprints)) == len(source_fingerprints)
  )
  if any(
    measurement.status
    is MocReflectedDomainAlternatingPhysicalFieldMeasurementStatus.SOURCE_FAILURE
    for measurement in measurements
  ):
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FAILURE,
      'one or more alternating source bands failed independent measurement',
      field_count=len(items),
      field_measurements=measurements,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=source_geometry_freshness_verified,
    )
  physical_fields = tuple(item.field for item in items)
  if any(
    not isinstance(field, MocPhysicalPostShockFieldResult)
    for field in physical_fields
  ):
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
      'every alternating result must retain a physical post-shock field',
      field_count=len(items),
      field_measurements=measurements,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=source_geometry_freshness_verified,
    )
  resolved_fields = tuple(
    field
    for field in physical_fields
    if isinstance(field, MocPhysicalPostShockFieldResult)
  )

  physical_field_chain_measurement = measure_moc_ambient_closed_physical_field_chain(
    resolved_fields,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    area_tolerance_m2=area_tolerance_m2,
    mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  handoff_link_count = max(0, len(items) - 1)
  handoff_links_verified: bool | None = None
  if handoff_link_count:
    handoff_links_verified = True
    for previous, current in zip(items[:-1], items[1:], strict=True):
      previous_field = previous.field
      assert isinstance(previous_field, MocPhysicalPostShockFieldResult)
      expected_handoff = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          previous_field.centerline_boundary_states,
          previous_field.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      handoff_links_verified = (
        handoff_links_verified and current.incoming_handoff == expected_handoff
      )

  fresh_domain_verified = physical_field_chain_measurement.fresh_domain_verified
  physical_closure_verified = bool(
    source_geometry_freshness_verified
    and handoff_links_verified is not False
    and fresh_domain_verified
    and all(measurement.physical_closure_verified for measurement in measurements)
    and physical_field_chain_measurement.physical_closure_verified
  )
  if not all(measurement.converged for measurement in measurements):
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
      'one or more alternating physical-field results failed independent measurement',
      field_count=len(items),
      field_measurements=measurements,
      physical_field_chain_measurement=physical_field_chain_measurement,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=source_geometry_freshness_verified,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
    )
  if not source_geometry_freshness_verified:
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FRESHNESS_FAILURE,
      'continued alternating cells must use fresh source-band state geometry',
      field_count=len(items),
      field_measurements=measurements,
      physical_field_chain_measurement=physical_field_chain_measurement,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=False,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
    )
  if handoff_links_verified is False:
    return _alternating_physical_field_chain_measurement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.HANDOFF_FAILURE,
      'continued alternating cells did not preserve the exact prior centerline handoff',
      field_count=len(items),
      field_measurements=measurements,
      physical_field_chain_measurement=physical_field_chain_measurement,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=True,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=False,
      fresh_domain_verified=fresh_domain_verified,
    )
  if not physical_field_chain_measurement.converged:
    status = (
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE
      if physical_field_chain_measurement.status
      is MocPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE
      else MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.FIELD_FAILURE
    )
    return _alternating_physical_field_chain_measurement_failure(
      status,
      'retained alternating physical fields failed the independent chain audit: '
      f'{physical_field_chain_measurement.message}',
      field_count=len(items),
      field_measurements=measurements,
      physical_field_chain_measurement=physical_field_chain_measurement,
      source_geometry_fingerprints=source_fingerprints,
      source_geometry_freshness_verified=True,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
    )
  return MocReflectedDomainAlternatingPhysicalFieldChainMeasurement(
    status=MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.CONVERGED,
    field_count=len(items),
    field_measurements=measurements,
    physical_field_chain_measurement=physical_field_chain_measurement,
    source_geometry_fingerprints=source_fingerprints,
    source_geometry_freshness_verified=True,
    handoff_link_count=handoff_link_count,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=True,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent alternating-source physical-field chain audit passed fresh '
      'source geometry, exact handoff, raw field, and fresh-domain checks; '
      'canonical reflected free-boundary closure remains pending'
    ),
  )
####


class MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus(str, Enum):
  """Outcome of comparing independently rerun alternating physical chains."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'resolution_failure'
  CASE_FAILURE = 'case_failure'
  CONSISTENCY_FAILURE = 'consistency_failure'
  SENSITIVITY_FAILURE = 'sensitivity_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase:
  """One independently rerun alternating physical-field chain.

  ``resolution`` is the physical shock sample count used for every result in
  ``results``.  The case owns typed solver results rather than serialized
  reports so the refinement operator can remeasure their source bands,
  upstream coupling, and raw physical fields independently.
  """

  resolution: int
  results: tuple[MocReflectedDomainAlternatingPhysicalFieldResult, ...]
  termination_reason: str | None = None
  physical_termination: bool | None = None

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 3
    ):
      raise ValueError('resolution must be an integer of at least three')
    try:
      results = tuple(self.results)
    except TypeError as error:
      raise TypeError(
        'results must contain MocReflectedDomainAlternatingPhysicalFieldResult values'
      ) from error
    if not results or any(
      not isinstance(result, MocReflectedDomainAlternatingPhysicalFieldResult)
      for result in results
    ):
      raise TypeError(
        'results must contain at least one alternating physical-field result'
      )
    object.__setattr__(self, 'results', results)
    reason = self.termination_reason
    if reason is not None:
      if isinstance(reason, Enum):
        reason = reason.value
      reason = str(reason)
      if not reason:
        raise ValueError('termination_reason must be non-empty when supplied')
      object.__setattr__(self, 'termination_reason', reason)
    if self.physical_termination is not None and not isinstance(
      self.physical_termination,
      bool,
    ):
      raise TypeError('physical_termination must be a bool or None')
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement:
  """Independent numerical-sensitivity evidence for alternating chains.

  Each case is remeasured through the single-chain alternating operator.  The
  comparison then checks fixed solver configuration, stable continued-cell
  count and geometry shape, exact handoff/fresh-domain evidence, strict shock
  pressure loss, and bounded changes in returned chain geometry.  A passing
  result is still research evidence: it does not close the canonical
  reflected free boundary or authorize a product claim.
  """

  status: MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_ALTERNATING_PHYSICAL_FIELD_CHAIN_REFINEMENT_OPERATOR_ID
  )
  cases: tuple[MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase, ...] = ()
  chain_measurements: tuple[
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurement, ...
  ] = ()
  resolutions: tuple[int, ...] = ()
  field_count: int | None = None
  resolution_order_verified: bool = False
  resolution_metadata_verified: bool = False
  field_count_consistent: bool = False
  geometry_shape_verified: bool = False
  solver_configuration_consistent: bool = False
  source_geometry_freshness_verified: bool = False
  pressure_loss_verified: bool = False
  handoff_metadata_complete: bool = False
  handoff_links_verified: bool | None = None
  fresh_domain_verified: bool = False
  termination_sensitivity_verified: bool | None = None
  axial_extent_residuals_m: tuple[float, ...] = ()
  shock_spacing_residuals_m: tuple[float, ...] = ()
  mesh_area_residuals_m2: tuple[float, ...] = ()
  maximum_radius_residuals_m: tuple[float, ...] = ()
  refinement_convergence_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    measurements = tuple(self.chain_measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and chain_measurements must have equal lengths')
    if any(
      not isinstance(
        case,
        MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain alternating physical-field refinement cases'
      )
    if any(
      not isinstance(
        measurement,
        MocReflectedDomainAlternatingPhysicalFieldChainMeasurement,
      )
      for measurement in measurements
    ):
      raise TypeError(
        'chain_measurements must contain alternating physical-field chain measurements'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'chain_measurements', measurements)
    object.__setattr__(
      self,
      'resolutions',
      tuple(case.resolution for case in cases),
    )
    for name in (
      'axial_extent_residuals_m',
      'shock_spacing_residuals_m',
      'mesh_area_residuals_m2',
      'maximum_radius_residuals_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    if self.field_count is not None and (
      isinstance(self.field_count, bool)
      or not isinstance(self.field_count, int)
      or self.field_count < 1
    ):
      raise ValueError('field_count must be positive when supplied')
    for name in (
      'resolution_order_verified',
      'resolution_metadata_verified',
      'field_count_consistent',
      'geometry_shape_verified',
      'solver_configuration_consistent',
      'source_geometry_freshness_verified',
      'pressure_loss_verified',
      'handoff_metadata_complete',
      'fresh_domain_verified',
      'refinement_convergence_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in ('handoff_links_verified', 'termination_sensitivity_verified'):
      value = getattr(self, name)
      if value is not None and not isinstance(value, bool):
        raise TypeError(f'{name} must be a bool or None')
  ####

  @property
  def converged(self) -> bool:
    return (
      self.status
      is MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONVERGED
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Keep numerical refinement evidence below the physical-closure gate."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_count': len(self.cases),
      'resolutions': list(self.resolutions),
      'field_count': self.field_count,
      'cases': [
        {
          'resolution': case.resolution,
          'termination_reason': case.termination_reason,
          'physical_termination': case.physical_termination,
          'result_count': len(case.results),
          'result_statuses': [result.status.value for result in case.results],
          'result_sample_counts': [result.sample_count for result in case.results],
          'measurement': measurement.as_report(),
        }
        for case, measurement in zip(self.cases, self.chain_measurements, strict=True)
      ],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'resolution_metadata_verified': self.resolution_metadata_verified,
        'field_count_consistent': self.field_count_consistent,
        'geometry_shape_verified': self.geometry_shape_verified,
        'solver_configuration_consistent': self.solver_configuration_consistent,
        'source_geometry_freshness_verified': (
          self.source_geometry_freshness_verified
        ),
        'pressure_loss_verified': self.pressure_loss_verified,
        'handoff_metadata_complete': self.handoff_metadata_complete,
        'handoff_links_verified': self.handoff_links_verified,
        'fresh_domain_verified': self.fresh_domain_verified,
        'termination_sensitivity_verified': self.termination_sensitivity_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
      },
      'residuals': {
        'axial_extent_residuals_m': list(self.axial_extent_residuals_m),
        'shock_spacing_residuals_m': list(self.shock_spacing_residuals_m),
        'mesh_area_residuals_m2': list(self.mesh_area_residuals_m2),
        'maximum_radius_residuals_m': list(self.maximum_radius_residuals_m),
      },
      'physical_closure_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _alternating_physical_field_chain_refinement_failure(
  status: MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase
  ] = (),
  chain_measurements: Sequence[
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurement
  ] = (),
  field_count: int | None = None,
  resolution_order_verified: bool = False,
  resolution_metadata_verified: bool = False,
  field_count_consistent: bool = False,
  geometry_shape_verified: bool = False,
  solver_configuration_consistent: bool = False,
  source_geometry_freshness_verified: bool = False,
  pressure_loss_verified: bool = False,
  handoff_metadata_complete: bool = False,
  handoff_links_verified: bool | None = None,
  fresh_domain_verified: bool = False,
  termination_sensitivity_verified: bool | None = None,
  axial_extent_residuals_m: Sequence[float] = (),
  shock_spacing_residuals_m: Sequence[float] = (),
  mesh_area_residuals_m2: Sequence[float] = (),
  maximum_radius_residuals_m: Sequence[float] = (),
  refinement_convergence_verified: bool = False,
) -> MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement:
  valid_cases = tuple(
    case
    for case in cases
    if isinstance(
      case,
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase,
    )
  )
  valid_measurements = tuple(
    measurement
    for measurement in chain_measurements
    if isinstance(
      measurement,
      MocReflectedDomainAlternatingPhysicalFieldChainMeasurement,
    )
  )
  paired_count = min(len(valid_cases), len(valid_measurements))
  return MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement(
    status=status,
    cases=valid_cases[:paired_count],
    chain_measurements=valid_measurements[:paired_count],
    field_count=field_count,
    resolution_order_verified=resolution_order_verified,
    resolution_metadata_verified=resolution_metadata_verified,
    field_count_consistent=field_count_consistent,
    geometry_shape_verified=geometry_shape_verified,
    solver_configuration_consistent=solver_configuration_consistent,
    source_geometry_freshness_verified=source_geometry_freshness_verified,
    pressure_loss_verified=pressure_loss_verified,
    handoff_metadata_complete=handoff_metadata_complete,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=fresh_domain_verified,
    termination_sensitivity_verified=termination_sensitivity_verified,
    axial_extent_residuals_m=tuple(axial_extent_residuals_m),
    shock_spacing_residuals_m=tuple(shock_spacing_residuals_m),
    mesh_area_residuals_m2=tuple(mesh_area_residuals_m2),
    maximum_radius_residuals_m=tuple(maximum_radius_residuals_m),
    refinement_convergence_verified=refinement_convergence_verified,
    message=message,
  )


def _alternating_physical_field_chain_geometry_metrics(
  measurement: MocReflectedDomainAlternatingPhysicalFieldChainMeasurement,
) -> tuple[tuple[float, float], tuple[float, ...], float, tuple[float, ...]] | None:
  """Extract comparable chain geometry from an independent chain audit."""

  physical = measurement.physical_field_chain_measurement
  if physical is None or len(physical.field_measurements) != measurement.field_count:
    return None
  fields = physical.field_measurements
  extents: list[tuple[float, float]] = []
  starts: list[float] = []
  radii: list[float] = []
  areas: list[float] = []
  for field in fields:
    if (
      field.axial_extent_m is None
      or field.shock_start_m is None
      or field.maximum_radius_m is None
      or field.mesh_area_m2 is None
    ):
      return None
    extent = (float(field.axial_extent_m[0]), float(field.axial_extent_m[1]))
    start_x = float(field.shock_start_m[0])
    radius = float(field.maximum_radius_m)
    area = float(field.mesh_area_m2)
    if (
      not all(isfinite(value) for value in extent)
      or not isfinite(start_x)
      or not isfinite(radius)
      or not isfinite(area)
      or area < 0.0
    ):
      return None
    extents.append(extent)
    starts.append(start_x)
    radii.append(radius)
    areas.append(area)
  spacing = tuple(
    current - previous
    for previous, current in zip(starts, starts[1:])
  )
  if any(not isfinite(value) for value in spacing):
    return None
  return (
    (min(extent[0] for extent in extents), max(extent[1] for extent in extents)),
    spacing,
    fsum(areas),
    tuple(radii),
  )


def measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
  cases: Sequence[
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase
  ],
  *,
  endpoint_tolerance_m: float = 2.0e-5,
  shock_spacing_tolerance_m: float = 1.0e-5,
  area_tolerance_m2: float = 2.0e-4,
  maximum_radius_tolerance_m: float = 2.0e-5,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement:
  """Compare independently rerun alternating physical chains by resolution.

  The operator never smooths, interpolates, or repairs a chain.  Each case is
  remeasured from its raw source-band and field results, and only exact chain
  geometry features that every case exposes are compared.  The resolution
  value is required to match each result's physical shock sample count; a
  caller cannot label an unchanged run as refinement evidence.
  """

  for name, value in (
    ('endpoint_tolerance_m', endpoint_tolerance_m),
    ('shock_spacing_tolerance_m', shock_spacing_tolerance_m),
    ('area_tolerance_m2', area_tolerance_m2),
    ('maximum_radius_tolerance_m', maximum_radius_tolerance_m),
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    items = tuple(cases)
  except TypeError:
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  if len(items) < 2:
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'at least two alternating physical-field refinement cases are required',
    )
  if any(
    not isinstance(
      case,
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase,
    )
    for case in items
  ):
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain alternating physical-field refinement cases',
      cases=items,
    )
  resolutions = tuple(case.resolution for case in items)
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
      cases=items,
    )

  chain_measurements = tuple(
    measure_moc_reflected_domain_alternating_physical_field_chain(
      case.results,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for case in items
  )
  if any(not measurement.converged for measurement in chain_measurements):
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CASE_FAILURE,
      'one or more alternating physical-field refinement cases failed independent measurement',
      cases=items,
      chain_measurements=chain_measurements,
      resolution_order_verified=True,
    )

  field_counts = tuple(measurement.field_count for measurement in chain_measurements)
  field_count_consistent = bool(
    field_counts
    and all(
      isinstance(count, int)
      and not isinstance(count, bool)
      and count > 0
      for count in field_counts
    )
    and len(set(field_counts)) == 1
  )
  field_count = field_counts[0] if field_count_consistent else None
  resolution_metadata_verified = all(
    result.sample_count == case.resolution
    for case in items
    for result in case.results
  )
  geometry_shapes = tuple(
    (
      measurement.field_count,
      None
      if measurement.physical_field_chain_measurement is None
      else len(measurement.physical_field_chain_measurement.field_measurements),
    )
    for measurement in chain_measurements
  )
  geometry_shape_verified = bool(
    field_count_consistent
    and len(set(geometry_shapes)) == 1
    and all(
      measurement.physical_field_chain_measurement is not None
      and len(measurement.physical_field_chain_measurement.field_measurements)
      == field_count
      for measurement in chain_measurements
    )
  )

  configurations = tuple(
    (
      result.compression_amplitude_rad,
      result.continuation_law,
      result.attachment_source,
      result.outer_source_index,
      result.position_tolerance_m,
      result.shock_angle_tolerance_rad,
    )
    for case in items
    for result in case.results
  )
  solver_configuration_consistent = bool(
    configurations and len(set(configurations)) == 1
  )
  source_geometry_freshness_verified = all(
    measurement.source_geometry_freshness_verified
    for measurement in chain_measurements
  )
  pressure_loss_verified = all(
    field_measurement.pressure_loss_verified is True
    for measurement in chain_measurements
    for field_measurement in (
      ()
      if measurement.physical_field_chain_measurement is None
      else measurement.physical_field_chain_measurement.field_measurements
    )
  )
  handoff_metadata_complete = all(
    measurement.handoff_links_verified is not None
    for measurement in chain_measurements
  )
  if all(measurement.handoff_link_count == 0 for measurement in chain_measurements):
    handoff_links_verified: bool | None = None
  else:
    handoff_links_verified = all(
      measurement.handoff_links_verified is True
      for measurement in chain_measurements
    )
  fresh_domain_verified = all(
    measurement.fresh_domain_verified
    for measurement in chain_measurements
  )

  if not (
    resolution_metadata_verified
    and field_count_consistent
    and geometry_shape_verified
    and solver_configuration_consistent
  ):
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONSISTENCY_FAILURE,
      'refinement cases must retain one solver configuration and continued-cell geometry shape',
      cases=items,
      chain_measurements=chain_measurements,
      field_count=field_count,
      resolution_order_verified=True,
      resolution_metadata_verified=resolution_metadata_verified,
      field_count_consistent=field_count_consistent,
      geometry_shape_verified=geometry_shape_verified,
      solver_configuration_consistent=solver_configuration_consistent,
      source_geometry_freshness_verified=source_geometry_freshness_verified,
      pressure_loss_verified=pressure_loss_verified,
      handoff_metadata_complete=handoff_metadata_complete,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
    )

  geometry_metrics = tuple(
    _alternating_physical_field_chain_geometry_metrics(measurement)
    for measurement in chain_measurements
  )
  if any(metrics is None for metrics in geometry_metrics):
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CASE_FAILURE,
      'alternating physical-field refinement cases must expose comparable raw chain geometry',
      cases=items,
      chain_measurements=chain_measurements,
      field_count=field_count,
      resolution_order_verified=True,
      resolution_metadata_verified=resolution_metadata_verified,
      field_count_consistent=field_count_consistent,
      geometry_shape_verified=geometry_shape_verified,
      solver_configuration_consistent=solver_configuration_consistent,
      source_geometry_freshness_verified=source_geometry_freshness_verified,
      pressure_loss_verified=pressure_loss_verified,
      handoff_metadata_complete=handoff_metadata_complete,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
    )
  resolved_metrics: tuple[
    tuple[tuple[float, float], tuple[float, ...], float, tuple[float, ...]],
    ...
  ] = tuple(
    metrics for metrics in geometry_metrics if metrics is not None
  )
  axial_extent_residuals = tuple(
    max(
      abs(current[0][0] - previous[0][0]),
      abs(current[0][1] - previous[0][1]),
    )
    for previous, current in zip(resolved_metrics, resolved_metrics[1:])
  )
  shock_spacing_residuals = tuple(
    max(
      (
        abs(current - previous)
        for previous, current in zip(
          previous_metrics[1],
          current_metrics[1],
          strict=True,
        )
      ),
      default=0.0,
    )
    for previous_metrics, current_metrics in zip(
      resolved_metrics,
      resolved_metrics[1:],
    )
  )
  mesh_area_residuals = tuple(
    abs(current_metrics[2] - previous_metrics[2])
    for previous_metrics, current_metrics in zip(
      resolved_metrics,
      resolved_metrics[1:],
    )
  )
  maximum_radius_residuals = tuple(
    max(
      (
        abs(current - previous)
        for previous, current in zip(
          previous_metrics[3],
          current_metrics[3],
          strict=True,
        )
      ),
      default=0.0,
    )
    for previous_metrics, current_metrics in zip(
      resolved_metrics,
      resolved_metrics[1:],
    )
  )
  termination_metadata = tuple(
    (case.termination_reason, case.physical_termination)
    for case in items
  )
  if not any(
    reason is not None or physical is not None
    for reason, physical in termination_metadata
  ):
    termination_sensitivity_verified = None
  elif any(
    reason is None or physical is None
    for reason, physical in termination_metadata
  ):
    termination_sensitivity_verified = False
  else:
    termination_sensitivity_verified = len(set(termination_metadata)) == 1

  refinement_convergence_verified = bool(
    resolution_metadata_verified
    and field_count_consistent
    and geometry_shape_verified
    and solver_configuration_consistent
    and source_geometry_freshness_verified
    and pressure_loss_verified
    and handoff_links_verified is not False
    and fresh_domain_verified
    and all(
      residual <= float(endpoint_tolerance_m)
      for residual in axial_extent_residuals
    )
    and all(
      residual <= float(shock_spacing_tolerance_m)
      for residual in shock_spacing_residuals
    )
    and all(
      residual <= float(area_tolerance_m2)
      for residual in mesh_area_residuals
    )
    and all(
      residual <= float(maximum_radius_tolerance_m)
      for residual in maximum_radius_residuals
    )
    and termination_sensitivity_verified is not False
  )
  common = {
    'cases': items,
    'chain_measurements': chain_measurements,
    'field_count': field_count,
    'resolution_order_verified': True,
    'resolution_metadata_verified': resolution_metadata_verified,
    'field_count_consistent': field_count_consistent,
    'geometry_shape_verified': geometry_shape_verified,
    'solver_configuration_consistent': solver_configuration_consistent,
    'source_geometry_freshness_verified': source_geometry_freshness_verified,
    'pressure_loss_verified': pressure_loss_verified,
    'handoff_metadata_complete': handoff_metadata_complete,
    'handoff_links_verified': handoff_links_verified,
    'fresh_domain_verified': fresh_domain_verified,
    'termination_sensitivity_verified': termination_sensitivity_verified,
    'axial_extent_residuals_m': axial_extent_residuals,
    'shock_spacing_residuals_m': shock_spacing_residuals,
    'mesh_area_residuals_m2': mesh_area_residuals,
    'maximum_radius_residuals_m': maximum_radius_residuals,
    'refinement_convergence_verified': refinement_convergence_verified,
  }
  if not refinement_convergence_verified:
    return _alternating_physical_field_chain_refinement_failure(
      MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.SENSITIVITY_FAILURE,
      'alternating physical-field chain geometry, pressure-loss, freshness, or termination sensitivity exceeded the declared tolerances',
      **common,
    )
  return MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurement(
    status=MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONVERGED,
    cases=items,
    chain_measurements=chain_measurements,
    field_count=field_count,
    resolution_order_verified=True,
    resolution_metadata_verified=True,
    field_count_consistent=True,
    geometry_shape_verified=True,
    solver_configuration_consistent=True,
    source_geometry_freshness_verified=True,
    pressure_loss_verified=True,
    handoff_metadata_complete=handoff_metadata_complete,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=True,
    termination_sensitivity_verified=termination_sensitivity_verified,
    axial_extent_residuals_m=axial_extent_residuals,
    shock_spacing_residuals_m=shock_spacing_residuals,
    mesh_area_residuals_m2=mesh_area_residuals,
    maximum_radius_residuals_m=maximum_radius_residuals,
    refinement_convergence_verified=True,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent alternating physical-field chains are stable across the '
      'declared shock resolutions; canonical reflected free-boundary closure '
      'and external validation remain pending'
    ),
  )
####


def _chain_failure(
  message: str,
  *,
  cells: Sequence[MocShockCellMeasurement] = (),
  handoff_link_count: int = 0,
  handoff_links_verified: bool | None = None,
  fresh_domain_verified: bool | None = None,
) -> MocShockCellChainMeasurement:
  return MocShockCellChainMeasurement(
    status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
    operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
    cells=tuple(cells),
    axial_extent_m=None,
    shock_start_spacing_m=(),
    total_mesh_area_m2=None,
    claim_status='not_accepted',
    message=message,
    handoff_link_count=handoff_link_count,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=fresh_domain_verified,
  )
####


def _handoff_link_audit(
  observations: Sequence[MocShockCellObservation],
) -> tuple[int, bool | None, str | None]:
  """Audit exact state/pressure handoffs when observations provide them.

  The geometry operator remains backwards compatible with observations that
  contain no chain handoff metadata.  Once any handoff is supplied, however,
  every adjacent link is required to expose the exact same typed samples and
  compatible boundary kind.  Equality is intentionally exact: a later cell
  must consume the prior solver result, not a re-sampled or re-labeled copy.
  """

  link_count = max(0, len(observations) - 1)
  metadata_present = any(
    item.incoming_handoff
    or item.outgoing_handoff
    or item.incoming_boundary_kind is not None
    or item.outgoing_boundary_kind is not None
    for item in observations
  )
  if not metadata_present:
    return link_count, None, None
  for index, (left, right) in enumerate(
    zip(observations, observations[1:]),
  ):
    if not left.outgoing_handoff or not right.incoming_handoff:
      return (
        link_count,
        False,
        f'chain handoff link {index} is missing an incoming or outgoing boundary',
      )
    if left.outgoing_handoff != right.incoming_handoff:
      return (
        link_count,
        False,
        f'chain handoff link {index} does not preserve exact state/pressure samples',
      )
    if (
      left.outgoing_boundary_kind is None
      or right.incoming_boundary_kind is None
    ):
      return (
        link_count,
        False,
        f'chain handoff link {index} is missing typed boundary-kind metadata',
      )
    if left.outgoing_boundary_kind is not right.incoming_boundary_kind:
      return (
        link_count,
        False,
        f'chain handoff link {index} changes boundary kind',
      )
  return link_count, True, None
####


def measure_moc_shock_cell_chain(
  observations: Sequence[MocShockCellObservation],
  *,
  position_tolerance_m: float = 1.0e-10,
  axis_tolerance_m: float = 1.0e-10,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocShockCellChainMeasurement:
  """Measure an ordered set of independently assembled MOC shock cells."""

  items = tuple(observations)
  if not items:
    return _chain_failure('at least one shock-cell observation is required')
  if any(not isinstance(item, MocShockCellObservation) for item in items):
    return _chain_failure('chain observations must be MocShockCellObservation values')
  indices = tuple(item.cell_index for item in items)
  if indices != tuple(range(1, len(items) + 1)):
    return _chain_failure('shock-cell observations must have contiguous one-based indices')
  handoff_link_count, handoff_links_verified, handoff_error = _handoff_link_audit(items)
  measurements = tuple(
    measure_moc_shock_cell(
      item,
      position_tolerance_m=position_tolerance_m,
      axis_tolerance_m=axis_tolerance_m,
      area_tolerance_m2=area_tolerance_m2,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    for item in items
  )
  if any(not measurement.converged for measurement in measurements):
    return MocShockCellChainMeasurement(
      status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
      operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
      cells=measurements,
      axial_extent_m=None,
      shock_start_spacing_m=(),
      total_mesh_area_m2=None,
      claim_status='not_accepted',
      message='one or more cell measurements failed; no chain metric was promoted',
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
    )
  if handoff_error is not None:
    return _chain_failure(
      handoff_error,
      cells=measurements,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=False,
    )
  extents = tuple(measurement.axial_extent_m for measurement in measurements)
  if any(extent is None for extent in extents):
    return _chain_failure('converged cell measurements must expose axial extents')
  resolved_extents = tuple(extent for extent in extents if extent is not None)
  if any(
      right[0] < left[1] - position_tolerance_m
      for left, right in zip(resolved_extents, resolved_extents[1:])
  ):
    return MocShockCellChainMeasurement(
      status=MocShockCellMeasurementStatus.CHAIN_FAILURE,
      operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
      cells=measurements,
      axial_extent_m=None,
      shock_start_spacing_m=(),
      total_mesh_area_m2=None,
      claim_status='not_accepted',
      message='continued shock-cell measurement extents overlap or reverse order',
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=False,
    )
  fresh_domain_verified = all(
    right[0] > left[1] + position_tolerance_m
    for left, right in zip(resolved_extents, resolved_extents[1:])
  )
  if not fresh_domain_verified:
    return _chain_failure(
      'continued shock-cell measurement domains must be strictly downstream '
      'of the preceding cell',
      cells=measurements,
      handoff_link_count=handoff_link_count,
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=False,
    )
  shock_starts = tuple(
    measurement.shock_start_m[0]
    for measurement in measurements
    if measurement.shock_start_m is not None
  )
  return MocShockCellChainMeasurement(
    status=MocShockCellMeasurementStatus.CONVERGED,
    operator_id=MOC_SHOCK_CELL_CHAIN_OPERATOR_ID,
    cells=measurements,
    axial_extent_m=(resolved_extents[0][0], resolved_extents[-1][1]),
    shock_start_spacing_m=tuple(
      right - left for left, right in zip(shock_starts, shock_starts[1:])
    ),
    total_mesh_area_m2=fsum(
      measurement.mesh_area_m2
      for measurement in measurements
      if measurement.mesh_area_m2 is not None
    ),
    claim_status='not_accepted',
    message=(
      'continued shock-cell geometry measured with independent per-cell '
      'topology checks; this does not establish physical chain closure'
    ),
    handoff_link_count=handoff_link_count,
    handoff_links_verified=handoff_links_verified,
    fresh_domain_verified=True,
  )
####


def measure_moc_ambient_closed_physical_field_chain(
  fields: Sequence[MocPhysicalPostShockFieldResult],
  *,
  position_tolerance_m: float = 1.0e-9,
  state_tolerance: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  area_tolerance_m2: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-12,
  intercell_bridge_endpoints_m: Sequence[tuple[Sequence[float], Sequence[float]]] | None = None,
) -> MocPhysicalFieldChainMeasurement:
  """Independently audit a sequence of solver-owned physical MOC fields.

  This operator is intentionally stricter than the planner trace audit.  It
  remeasures every field from its raw mesh and retained state arrays, then
  checks that each next field consumes the previous centerline trace exactly
  and either starts at the previous ambient endpoint or supplies an explicit
  reflected/source bridge whose measured endpoints join those two domains. It does not use
  ``physical_closure_verified``, ``state_sampling_available``,
  ``upstream_shock_coupling_verified``, or ``pressure_loss_verified`` as proof.
  A passing result is still research evidence, not a canonical reflected
  free-boundary or externally validated shock train.
  """

  try:
    items = tuple(fields)
  except TypeError:
    return MocPhysicalFieldChainMeasurement(
      status=MocPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      field_count=0,
      message='fields must be an iterable of MocPhysicalPostShockFieldResult values',
    )
  if not items:
    return MocPhysicalFieldChainMeasurement(
      status=MocPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      message='at least one physical post-shock field is required',
    )
  if any(not isinstance(field, MocPhysicalPostShockFieldResult) for field in items):
    return MocPhysicalFieldChainMeasurement(
      status=MocPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
      field_count=len(items),
      field_statuses=('invalid_input',) * len(items),
      field_topology_verified=(False,) * len(items),
      field_ambient_boundary_verified=(False,) * len(items),
      field_state_sampling_verified=(False,) * len(items),
      field_upstream_shock_coupling_verified=(False,) * len(items),
      field_physical_closure_verified=(False,) * len(items),
      message='fields must contain only MocPhysicalPostShockFieldResult values',
    )
  resolved_bridge_endpoints: tuple[tuple[Point, Point], ...] = ()
  if intercell_bridge_endpoints_m is not None:
    try:
      raw_bridge_endpoints = tuple(intercell_bridge_endpoints_m)
      if len(raw_bridge_endpoints) != max(0, len(items) - 1):
        return MocPhysicalFieldChainMeasurement(
          status=MocPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
          field_count=len(items),
          message=(
            'intercell_bridge_endpoints_m must contain exactly one bridge '
            'for each adjacent field pair'
          ),
        )
      normalized_bridges: list[tuple[Point, Point]] = []
      for endpoints in raw_bridge_endpoints:
        if len(endpoints) != 2:
          raise ValueError('bridge endpoints must be (start, end) pairs')
        start, end = endpoints
        start_point = (float(start[0]), float(start[1]))
        end_point = (float(end[0]), float(end[1]))
        if not all(
          isfinite(value)
          for value in (*start_point, *end_point)
        ):
          raise ValueError('bridge endpoints must contain finite coordinates')
        normalized_bridges.append((start_point, end_point))
      resolved_bridge_endpoints = tuple(normalized_bridges)
    except (IndexError, TypeError, ValueError):
      return MocPhysicalFieldChainMeasurement(
        status=MocPhysicalFieldChainMeasurementStatus.INVALID_INPUT,
        field_count=len(items),
        message=(
          'intercell_bridge_endpoints_m must contain finite (start, end) '
          'coordinate pairs'
        ),
      )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('area_tolerance_m2', area_tolerance_m2),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  statuses: list[str] = []
  topology_verified: list[bool] = []
  ambient_boundary_verified: list[bool] = []
  state_sampling_verified: list[bool] = []
  upstream_coupling_verified: list[bool] = []
  physical_closure_verified: list[bool] = []
  measurements: list[MocShockCellMeasurement] = []
  reference_ambient_pressure: float | None = None
  explicit_bridge_requested = intercell_bridge_endpoints_m is not None
  explicit_bridges_verified = True

  def failure(
    status: MocPhysicalFieldChainMeasurementStatus,
    message: str,
    *,
    handoff_links_verified: bool | None = None,
    fresh_domain_verified: bool = False,
  ) -> MocPhysicalFieldChainMeasurement:
    return MocPhysicalFieldChainMeasurement(
      status=status,
      field_count=len(items),
      field_measurements=tuple(measurements),
      field_statuses=tuple(statuses),
      field_topology_verified=tuple(topology_verified),
      field_ambient_boundary_verified=tuple(ambient_boundary_verified),
      field_state_sampling_verified=tuple(state_sampling_verified),
      field_upstream_shock_coupling_verified=tuple(upstream_coupling_verified),
      field_physical_closure_verified=tuple(physical_closure_verified),
      handoff_link_count=max(0, len(statuses) - 1),
      handoff_links_verified=handoff_links_verified,
      fresh_domain_verified=fresh_domain_verified,
      intercell_bridge_count=len(resolved_bridge_endpoints),
      intercell_bridge_endpoints_m=resolved_bridge_endpoints,
      intercell_bridges_verified=explicit_bridges_verified,
      physical_closure_verified=False,
      message=message,
    )

  def close(
    actual: float,
    expected: float,
    tolerance: float,
    *,
    relative: bool = False,
  ) -> bool:
    scale = (
      max(1.0, abs(float(actual)), abs(float(expected)))
      if relative else 1.0
    )
    return abs(float(actual) - float(expected)) <= tolerance * scale

  def state_matches(
    state: object,
    point: Point,
    *,
    require_axis: bool = False,
  ) -> bool:
    if not isinstance(state, CharacteristicState):
      return False
    return bool(
      close(state.x_m, point[0], position_tolerance_m)
      and close(state.y_m, point[1], position_tolerance_m)
      and (not require_axis or abs(state.y_m) <= position_tolerance_m)
    )

  def state_values_match(left: object, right: object) -> bool:
    if not isinstance(left, CharacteristicState) or not isinstance(
      right,
      CharacteristicState,
    ):
      return False
    return bool(
      close(left.x_m, right.x_m, position_tolerance_m)
      and close(left.y_m, right.y_m, position_tolerance_m)
      and close(left.theta_rad, right.theta_rad, state_tolerance)
      and close(left.mach, right.mach, state_tolerance)
      and close(left.gamma, right.gamma, state_tolerance)
    )

  def positive_pressures(values: Sequence[float]) -> bool:
    try:
      return all(isfinite(float(value)) and float(value) > 0.0 for value in values)
    except (TypeError, ValueError):
      return False

  def sequence_matches(
    actual: Sequence[float],
    expected: Sequence[float],
    tolerance: float,
    *,
    relative: bool = False,
  ) -> bool:
    try:
      return len(actual) == len(expected) and all(
        close(value, reference, tolerance, relative=relative)
        for value, reference in zip(actual, expected, strict=True)
      )
    except (TypeError, ValueError):
      return False

  for field_index, field in enumerate(items, start=1):
    raw_status = field.status
    statuses.append(
      raw_status.value
      if isinstance(raw_status, MocPhysicalPostShockFieldStatus)
      else str(raw_status)
    )
    topology_verified.append(False)
    ambient_boundary_verified.append(False)
    state_sampling_verified.append(False)
    upstream_coupling_verified.append(False)
    physical_closure_verified.append(False)

    if raw_status is not MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} did not report a converged ambient-closed result',
      )

    try:
      nodes = tuple(field.nodes)
      cells = tuple(field.cells)
      shock_points = _points(field.shock_boundary_points_m, 'shock boundary')
      ambient_points = _points(
        field.ambient_boundary_points_m,
        'ambient boundary',
      )
      centerline_points = _points(
        field.centerline_boundary_points_m,
        'centerline boundary',
      )
    except (TypeError, ValueError, AttributeError) as error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} raw geometry could not be read: {error}',
      )
    if not nodes or not cells or any(
      not isinstance(cell, MocCharacteristicCell) for cell in cells
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} must retain typed nodes and characteristic cells',
      )
    try:
      topology = validate_moc_mesh(
        cells,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.TOPOLOGY_FAILURE,
        f'physical field {field_index} topology could not be remeasured: {error}',
      )
    if not (
      topology.connected
      and topology.forms_closed_zone
      and topology.nonmanifold_edge_count == 0
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.TOPOLOGY_FAILURE,
        f'physical field {field_index} failed the independent mesh topology check: '
        f'{topology.message}',
      )
    topology_verified[-1] = True

    if len(shock_points) < 3 or len(ambient_points) != len(shock_points):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} must pair at least three shock and ambient samples',
      )
    shock_error = _validate_polyline(
      shock_points,
      'shock boundary',
      position_tolerance_m=position_tolerance_m,
      require_strict_x=True,
    )
    centerline_error = _validate_polyline(
      centerline_points,
      'centerline boundary',
      position_tolerance_m=position_tolerance_m,
      require_strict_x=False,
    )
    if shock_error or centerline_error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} boundary geometry failed: '
        f'{shock_error or centerline_error}',
      )
    if (
      hypot(
        shock_points[-1][0] - centerline_points[0][0],
        shock_points[-1][1] - centerline_points[0][1],
      ) > position_tolerance_m
      or hypot(
        shock_points[0][0] - ambient_points[0][0],
        shock_points[0][1] - ambient_points[0][1],
      ) > position_tolerance_m
      or any(abs(point[1]) > position_tolerance_m for point in centerline_points)
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} shock/ambient/centerline seam is not a valid axis closure',
      )
    try:
      edge_counts, _vertex_points = _edge_counts(
        cells,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.TOPOLOGY_FAILURE,
        f'physical field {field_index} perimeter could not be remeasured: {error}',
      )
    if not all(
      _polyline_has_boundary_edges(
        path,
        edge_counts,
        vertex_tolerance_m=mesh_vertex_tolerance_m,
      )
      for path in (shock_points, ambient_points, centerline_points)
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} is missing an explicit shock, ambient, or centerline perimeter path',
      )

    upstream_states = tuple(field.upstream_shock_boundary_states)
    upstream_pressures = tuple(field.upstream_shock_boundary_total_pressure_Pa)
    post_shock_states = tuple(field.post_shock_boundary_states)
    post_shock_pressures = tuple(field.post_shock_boundary_total_pressure_Pa)
    centerline_states = tuple(field.centerline_boundary_states)
    centerline_pressures = tuple(field.centerline_boundary_total_pressure_Pa)
    if (
      len(upstream_states) != len(shock_points)
      or len(upstream_pressures) != len(shock_points)
      or len(post_shock_states) != len(shock_points)
      or len(post_shock_pressures) != len(shock_points)
      or len(centerline_states) != len(centerline_points)
      or len(centerline_pressures) != len(centerline_points)
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} does not retain complete boundary state arrays',
      )
    if not (
      positive_pressures(upstream_pressures)
      and positive_pressures(post_shock_pressures)
      and positive_pressures(centerline_pressures)
      and all(
        state_matches(state, point)
        for state, point in zip(upstream_states, shock_points, strict=True)
      )
      and all(
        state_matches(state, point)
        for state, point in zip(post_shock_states, shock_points, strict=True)
      )
      and all(
        state_matches(state, point, require_axis=True)
        and abs(state.theta_rad) <= state_tolerance
        for state, point in zip(centerline_states, centerline_points, strict=True)
      )
      and all(
        second[0] > first[0] + position_tolerance_m
        for first, second in zip(centerline_points, centerline_points[1:])
      )
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} boundary state sampling is inconsistent',
      )
    upstream_coupling_verified[-1] = True

    boundary = field.ambient_boundary
    if not isinstance(boundary, MocAmbientPressureBoundaryResult):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} did not retain an ambient boundary result',
      )
    boundary_points = tuple(boundary.points_m)
    boundary_states = tuple(boundary.states)
    boundary_pressures = tuple(boundary.total_pressure_Pa)
    ambient_pressure = boundary.ambient_pressure_Pa
    if (
      ambient_pressure is None
      or not isfinite(float(ambient_pressure))
      or float(ambient_pressure) <= 0.0
      or len(boundary_points) != len(ambient_points)
      or len(boundary_states) != len(ambient_points)
      or len(boundary_pressures) != len(ambient_points)
      or not positive_pressures(boundary_pressures)
      or any(
        not state_matches(state, point)
        for state, point in zip(boundary_states, ambient_points, strict=True)
      )
      or any(
        hypot(point[0] - boundary_point[0], point[1] - boundary_point[1])
        > position_tolerance_m
        for point, boundary_point in zip(
          ambient_points,
          boundary_points,
          strict=True,
        )
      )
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} ambient boundary samples are inconsistent',
      )
    try:
      ambient_samples = tuple(
        MocAmbientBoundarySample(
          point_m=point,
          state=state,
          total_pressure_Pa=pressure,
        )
        for point, state, pressure in zip(
          ambient_points,
          boundary_states,
          boundary_pressures,
          strict=True,
        )
      )
      independent_boundary = validate_ambient_pressure_boundary(
        ambient_samples,
        float(ambient_pressure),
        position_tolerance_m=position_tolerance_m,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} ambient boundary could not be remeasured: {error}',
      )
    raw_boundary_consistent = bool(
      independent_boundary.converged
      and sequence_matches(
        boundary.static_pressure_Pa,
        independent_boundary.static_pressure_Pa,
        pressure_tolerance,
        relative=True,
      )
      and sequence_matches(
        boundary.pressure_residuals,
        independent_boundary.pressure_residuals,
        pressure_tolerance,
      )
      and sequence_matches(
        boundary.tangent_residuals,
        independent_boundary.tangent_residuals,
        tangent_tolerance,
      )
    )
    if not raw_boundary_consistent:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        f'physical field {field_index} ambient pressure/tangency gates failed independent measurement',
      )
    ambient_boundary_verified[-1] = True
    if reference_ambient_pressure is None:
      reference_ambient_pressure = float(ambient_pressure)
    elif not close(
      float(ambient_pressure),
      reference_ambient_pressure,
      pressure_tolerance,
      relative=True,
    ):
      return failure(
        MocPhysicalFieldChainMeasurementStatus.BOUNDARY_FAILURE,
        'continued physical fields changed the ambient pressure reference',
      )

    node_residuals_geometry: list[float] = []
    node_residuals_invariant: list[float] = []
    node_sampling_verified = True
    for node in nodes:
      if not isinstance(node, MocCharacteristicNode):
        node_sampling_verified = False
        continue
      point_result = node.point_result
      node_pressure = node.total_pressure_Pa
      node_ok = bool(
        isinstance(point_result, CharacteristicPointResult)
        and point_result.converged
        and state_matches(node.state, node.point_m)
        and state_values_match(node.state, point_result.state)
        and isinstance(point_result.point_m, tuple)
        and len(point_result.point_m) == 2
        and state_matches(point_result.state, point_result.point_m)
        and close(point_result.point_m[0], node.point_m[0], position_tolerance_m)
        and close(point_result.point_m[1], node.point_m[1], position_tolerance_m)
        and node_pressure is not None
        and isfinite(float(node_pressure))
        and float(node_pressure) > 0.0
      )
      if node_ok:
        geometry_residual = point_result.geometry_residual
        invariant_residuals = (
          point_result.invariant_residual_plus,
          point_result.invariant_residual_minus,
        )
        if (
          geometry_residual is None
          or not isfinite(float(geometry_residual))
          or abs(float(geometry_residual)) > invariant_tolerance
          or any(
            value is None
            or not isfinite(float(value))
            or abs(float(value)) > invariant_tolerance
            for value in invariant_residuals
          )
        ):
          node_ok = False
        else:
          node_residuals_geometry.append(abs(float(geometry_residual)))
          for value in invariant_residuals:
            if value is not None:
              node_residuals_invariant.append(abs(float(value)))
      node_sampling_verified = node_sampling_verified and node_ok
    source_samples: list[tuple[Point, CharacteristicState, float]] = [
      ((state.x_m, state.y_m), state, pressure)
      for state, pressure in zip(
        post_shock_states,
        post_shock_pressures,
        strict=True,
      )
    ]
    source_samples.extend(
      (point, state, pressure)
      for point, state, pressure in zip(
        boundary_points,
        boundary_states,
        boundary_pressures,
        strict=True,
      )
    )
    source_samples.extend(
      (point, state, pressure)
      for point, state, pressure in zip(
        centerline_points,
        centerline_states,
        centerline_pressures,
        strict=True,
      )
    )
    source_samples.extend(
      (node.point_m, node.state, float(node.total_pressure_Pa))
      for node in nodes
      if node.total_pressure_Pa is not None
    )
    for cell in cells:
      try:
        vertices = _cell_vertices(cell)
      except (AttributeError, TypeError, ValueError):
        node_sampling_verified = False
        break
      for vertex in vertices:
        if not any(
          hypot(vertex[0] - point[0], vertex[1] - point[1])
          <= mesh_vertex_tolerance_m
          and pressure is not None
          and isfinite(float(pressure))
          and float(pressure) > 0.0
          for point, _state, pressure in source_samples
        ):
          node_sampling_verified = False
          break
      if not node_sampling_verified:
        break
    state_sampling_verified[-1] = node_sampling_verified
    if not node_sampling_verified:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} does not retain a bounded state and pressure sample for every mesh vertex',
      )

    summary_residuals_verified = bool(
      field.maximum_geometry_residual_m is not None
      and field.maximum_absolute_invariant_residual is not None
      and isfinite(float(field.maximum_geometry_residual_m))
      and isfinite(float(field.maximum_absolute_invariant_residual))
      and 0.0 <= float(field.maximum_geometry_residual_m) <= invariant_tolerance
      and 0.0 <= float(field.maximum_absolute_invariant_residual) <= invariant_tolerance
      and float(field.maximum_geometry_residual_m)
      >= max(node_residuals_geometry, default=0.0) - invariant_tolerance
      and float(field.maximum_absolute_invariant_residual)
      >= max(node_residuals_invariant, default=0.0) - invariant_tolerance
    )
    pressure_ratios = tuple(
      downstream / upstream
      for upstream, downstream in zip(
        upstream_pressures,
        post_shock_pressures,
        strict=True,
      )
    )
    strict_pressure_loss = all(0.0 < ratio < 1.0 for ratio in pressure_ratios)
    if not strict_pressure_loss:
      start_allowed = bool(
        field.zero_strength_shock_start_allowed
        and abs(pressure_ratios[0] - 1.0) <= pressure_tolerance
        and all(0.0 < ratio < 1.0 for ratio in pressure_ratios[1:])
      )
      endpoints_allowed = bool(
        field.zero_strength_shock_endpoints_allowed
        and abs(pressure_ratios[0] - 1.0) <= pressure_tolerance
        and abs(pressure_ratios[-1] - 1.0) <= pressure_tolerance
        and all(0.0 < ratio < 1.0 for ratio in pressure_ratios[1:-1])
      )
      strict_pressure_loss = start_allowed or endpoints_allowed
    raw_physical_closure = bool(
      summary_residuals_verified
      and strict_pressure_loss
      and independent_boundary.converged
    )
    if not raw_physical_closure:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} failed independent residual or shock-loss closure gates',
      )

    try:
      incoming_states = tuple(field.incoming_handoff_states)
      incoming_pressures = tuple(field.incoming_handoff_total_pressure_Pa)
      incoming = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(incoming_states, incoming_pressures, strict=True)
      )
      outgoing = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(centerline_states, centerline_pressures, strict=True)
      )
      observation = MocShockCellObservation(
        cell_index=field_index,
        shock_boundary_points_m=shock_points,
        centerline_boundary_points_m=centerline_points,
        cells=cells,
        upstream_total_pressure_Pa=upstream_pressures,
        downstream_total_pressure_Pa=post_shock_pressures,
        incoming_handoff=incoming,
        outgoing_handoff=outgoing,
        incoming_boundary_kind=(
          MocChainBoundaryKind.CENTERLINE_TRACE if incoming else None
        ),
        outgoing_boundary_kind=MocChainBoundaryKind.CENTERLINE_TRACE,
        zero_strength_shock_start_allowed=field.zero_strength_shock_start_allowed,
        zero_strength_shock_endpoints_allowed=field.zero_strength_shock_endpoints_allowed,
      )
    except (TypeError, ValueError) as error:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.HANDOFF_FAILURE,
        f'physical field {field_index} handoff data could not be assembled: {error}',
      )
    measurement = measure_moc_shock_cell(
      observation,
      position_tolerance_m=position_tolerance_m,
      axis_tolerance_m=position_tolerance_m,
      area_tolerance_m2=area_tolerance_m2,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    )
    measurements.append(measurement)
    if not measurement.converged:
      return failure(
        MocPhysicalFieldChainMeasurementStatus.FIELD_FAILURE,
        f'physical field {field_index} failed independent shock-cell measurement: '
        f'{measurement.message}',
      )
    physical_closure_verified[-1] = True

    if field_index > 1:
      previous = items[field_index - 2]
      expected_incoming = tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          previous.centerline_boundary_states,
          previous.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      if incoming != expected_incoming:
        return failure(
          MocPhysicalFieldChainMeasurementStatus.HANDOFF_FAILURE,
          f'physical field {field_index} changed the exact previous centerline handoff',
          handoff_links_verified=False,
        )
      try:
        previous_end_x = float(previous.ambient_boundary_points_m[-1][0])
        current_vertices = tuple(
          vertex
          for cell in cells
          for vertex in _cell_vertices(cell)
        )
        current_min_x = min(vertex[0] for vertex in current_vertices)
        current_max_x = max(vertex[0] for vertex in current_vertices)
      except (AttributeError, TypeError, ValueError) as error:
        return failure(
          MocPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE,
          f'physical field {field_index} domain extent could not be measured: {error}',
          handoff_links_verified=True,
        )
      if explicit_bridge_requested:
        bridge_start, bridge_end = resolved_bridge_endpoints[field_index - 2]
        bridge_ok = bool(
          close(
            bridge_start[0],
            previous.ambient_boundary_points_m[-1][0],
            position_tolerance_m,
          )
          and close(
            bridge_start[1],
            previous.ambient_boundary_points_m[-1][1],
            position_tolerance_m,
          )
          and close(bridge_end[0], shock_points[0][0], position_tolerance_m)
          and close(bridge_end[1], shock_points[0][1], position_tolerance_m)
          and close(bridge_end[0], ambient_points[0][0], position_tolerance_m)
          and close(bridge_end[1], ambient_points[0][1], position_tolerance_m)
          and bridge_end[0] > bridge_start[0] + position_tolerance_m
          and current_min_x >= bridge_end[0] - position_tolerance_m
          and current_max_x > bridge_end[0] + position_tolerance_m
        )
        explicit_bridges_verified = explicit_bridges_verified and bridge_ok
        if not bridge_ok:
          return failure(
            MocPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE,
            (
              f'physical field {field_index} does not join its previous '
              'domain through the supplied explicit intercell bridge'
            ),
            handoff_links_verified=True,
          )
      elif (
        abs(shock_points[0][0] - previous_end_x) > position_tolerance_m
        or abs(ambient_points[0][0] - previous_end_x) > position_tolerance_m
        or current_min_x < previous_end_x - position_tolerance_m
        or current_max_x <= previous_end_x + position_tolerance_m
      ):
        return failure(
          MocPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE,
          f'physical field {field_index} does not begin at a fresh downstream ambient interface',
          handoff_links_verified=True,
        )

  handoff_link_count = max(0, len(items) - 1)
  return MocPhysicalFieldChainMeasurement(
    status=MocPhysicalFieldChainMeasurementStatus.CONVERGED,
    field_count=len(items),
    field_measurements=tuple(measurements),
    field_statuses=tuple(statuses),
    field_topology_verified=tuple(topology_verified),
    field_ambient_boundary_verified=tuple(ambient_boundary_verified),
    field_state_sampling_verified=tuple(state_sampling_verified),
    field_upstream_shock_coupling_verified=tuple(upstream_coupling_verified),
    field_physical_closure_verified=tuple(physical_closure_verified),
    handoff_link_count=handoff_link_count,
    handoff_links_verified=True if handoff_link_count else None,
    fresh_domain_verified=True,
    intercell_bridge_count=len(resolved_bridge_endpoints),
    intercell_bridge_endpoints_m=resolved_bridge_endpoints,
    intercell_bridges_verified=explicit_bridges_verified,
    physical_closure_verified=True,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent ambient-closed physical-field chain audit passed raw mesh, '
      'boundary, state-sampling, shock-loss, exact-handoff, and fresh-domain '
      'checks; canonical reflected free-boundary closure and external '
      'validation remain pending'
    ),
  )
####
