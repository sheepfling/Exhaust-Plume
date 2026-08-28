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
from math import atan2, cos, fsum, hypot, isfinite, log, pi, sin, sqrt
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
  validate_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
)
from exhaust_plume.models.moc.caustic_bridge import (
  MocCausticUpstreamBridge,
  sample_caustic_upstream_bridge,
)
from exhaust_plume.models.moc.caustic_remesh import (
  MocCausticShockRemeshRequest,
  MocCausticShockRemeshResult,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocCellClosureStatus,
  MocChainGeometryFidelity,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.planner import MocChainPlannerResult
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.post_shock import (
  MocPostShockBoundaryState,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldStatus,
  MocShockBoundaryFitResult,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.shock_chain import MocTerminalShockCellFieldResult
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicNode
from exhaust_plume.models.moc.free_boundary import MocFreeBoundaryShockResult
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MOC_CAUSTIC_REMESH_OPERATOR_ID',
  'MOC_CHAIN_PLANNER_OPERATOR_ID',
  'MOC_MIXED_REGIME_FREE_BOUNDARY_OPERATOR_ID',
  'MOC_MIXED_REGIME_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MOC_MIXED_REGIME_CONTROL_SECTION_OPERATOR_ID',
  'MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID',
  'MOC_SHOCK_CELL_CHAIN_OPERATOR_ID',
  'MOC_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID',
  'MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID',
  'MOC_TERMINAL_CLOSURE_OPERATOR_ID',
  'MocCausticRemeshMeasurement',
  'MocCausticRemeshMeasurementStatus',
  'MocCausticRemeshObservation',
  'MocChainPlannerMeasurement',
  'MocChainPlannerMeasurementStatus',
  'MocMixedRegimePotentialMeasurement',
  'MocMixedRegimePotentialMeasurementStatus',
  'MocMixedRegimeFreeBoundaryMeasurement',
  'MocMixedRegimeFreeBoundaryMeasurementStatus',
  'MocMixedRegimeFreeBoundaryRefinementCase',
  'MocMixedRegimeFreeBoundaryRefinementMeasurement',
  'MocMixedRegimeFreeBoundaryRefinementMeasurementStatus',
  'MocMixedRegimeControlSectionMeasurement',
  'MocMixedRegimeControlSectionMeasurementStatus',
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
  'measure_moc_caustic_remesh',
  'measure_moc_chain_planner',
  'measure_mixed_regime_compressible_potential_field',
  'measure_mixed_regime_free_boundary_reference',
  'measure_mixed_regime_free_boundary_refinement',
  'measure_mixed_regime_control_section',
  'measure_moc_terminal_closure',
  'measure_moc_shock_cell',
  'measure_moc_shock_cell_chain',
  'measure_moc_shock_cell_chain_refinement',
)


MOC_SHOCK_CELL_GEOMETRY_OPERATOR_ID = 'op.moc.shock-cell-geometry'
MOC_SHOCK_CELL_CHAIN_OPERATOR_ID = 'op.moc.shock-cell-chain'
MOC_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.shock-cell-chain-refinement'
)
MOC_TERMINAL_CLOSURE_OPERATOR_ID = 'op.moc.terminal-closure'
MOC_CAUSTIC_REMESH_OPERATOR_ID = 'op.moc.caustic-remesh'
MOC_CHAIN_PLANNER_OPERATOR_ID = 'op.moc.chain-planner'
MOC_MIXED_REGIME_FREE_BOUNDARY_OPERATOR_ID = (
  'op.moc.mixed-regime-free-boundary-reference'
)
MOC_MIXED_REGIME_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.mixed-regime-free-boundary-refinement'
)
MOC_MIXED_REGIME_CONTROL_SECTION_OPERATOR_ID = (
  'op.moc.mixed-regime-control-section'
)
MOC_MIXED_REGIME_POTENTIAL_OPERATOR_ID = 'op.moc.mixed-regime-compressible-potential'

Point = tuple[float, float]


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
      },
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
  residuals.  It deliberately reports the mesh divergence diagnostic without
  using it as a gate: this reference is quasi-one-dimensional, so that value
  is not evidence of a full two-dimensional MOC or Navier--Stokes field.
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
  return (
    len(ratios),
    min(ratios),
    max(ratios),
    loss_verified,
    None if loss_verified else 'every shock sample must reduce total pressure',
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
      potential_circulation_residual=circulation_residual,
      maximum_mach=maximum_mach,
      message=(
        'independent compressible potential residual gate failed: '
        f'thermodynamic={thermodynamic_residual}, mass={mass_residual}, '
        f'boundary_velocity={boundary_velocity_residual}, '
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
    potential_circulation_residual=circulation_residual,
    maximum_mach=maximum_mach,
    nonlinear_iteration_count=field.nonlinear_iteration_count,
    message=(
      'independent compressible potential measurement passed the explicit '
      'perimeter, radial layout, nonlinear mass, circulation, and subsonic '
      'gates; it remains a non-canonical scalar reference'
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
  if result.model != expected_field_model:
    return _free_boundary_measurement_failure(
      MocMixedRegimeFreeBoundaryMeasurementStatus.INVALID_INPUT,
      result=result,
      message=(
        'free-boundary measurement requires the explicitly named scalar-field '
        f'model, received {result.model!r}'
      ),
    )
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
      mixed_regime_model_verified = bool(
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
