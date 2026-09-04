"""Independent audit for the global reflected mixed-regime boundary bridge.

The solver-side bridge is intentionally a scalar variable-entropy reference.
This module audits its provenance and retained fields as data: it does not run
the reference solver, infer a perimeter, or turn a successful audit into a
canonical reflected-MOC or production-chain claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite, sqrt
from types import MappingProxyType
from typing import Any, Sequence

from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  MocReflectedDomainGlobalPhysicalClosureStatus,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MIXED_REGIME_BOUNDARY_MODEL,
  MocReflectedDomainMixedRegimeBoundaryRequest,
  MocReflectedDomainMixedRegimeBoundaryResult,
  MocReflectedDomainMixedRegimeBoundaryStatus,
  build_reflected_domain_mixed_regime_boundary_request,
  solve_reflected_domain_mixed_regime_boundary,
)
from exhaust_plume.models.moc.mixed_regime_variable_entropy import (
  MocMixedRegimeVariableEntropyFreeBoundaryResult,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeVariableEntropyFreeBoundaryMeasurement,
  measure_mixed_regime_variable_entropy_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_OPERATOR_ID',
  'MocReflectedDomainMixedRegimeBoundaryMeasurementStatus',
  'MocReflectedDomainMixedRegimeBoundaryMeasurement',
  'measure_reflected_domain_mixed_regime_boundary',
  'MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainMixedRegimeBoundaryRefinementStatus',
  'MocReflectedDomainMixedRegimeBoundaryRefinementCase',
  'MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement',
  'measure_reflected_domain_mixed_regime_boundary_refinement',
  'MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainMixedRegimeBoundaryRefinementRun',
  'run_reflected_domain_mixed_regime_boundary_refinement',
)


MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_OPERATOR_ID = (
  'op.moc.reflected-domain-mixed-regime-boundary'
)

MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain-mixed-regime-boundary-refinement'
)

MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain-mixed-regime-boundary-refinement-run'
)


class MocReflectedDomainMixedRegimeBoundaryMeasurementStatus(str, Enum):
  """Outcome of independently measuring the mixed-regime bridge."""

  CONVERGED = 'converged-global-mixed-regime-boundary-measurement'
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_FAILURE = 'upstream-closure-measurement-failure'
  REQUEST_FAILURE = 'mixed-regime-request-measurement-failure'
  TERMINAL_FAILURE = 'mixed-regime-terminal-measurement-failure'
  HANDOFF_FAILURE = 'mixed-regime-handoff-measurement-failure'
  CONTROL_SECTION_FAILURE = 'mixed-regime-control-section-measurement-failure'
  FIELD_FAILURE = 'mixed-regime-reference-field-measurement-failure'
  RESIDUAL_FAILURE = 'mixed-regime-residual-measurement-failure'
  CONSISTENCY_FAILURE = 'mixed-regime-reported-field-consistency-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryMeasurement:
  """Independent provenance, boundary, and residual evidence."""

  status: MocReflectedDomainMixedRegimeBoundaryMeasurementStatus
  operator_id: str = MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_OPERATOR_ID
  candidate: MocReflectedDomainMixedRegimeBoundaryResult | None = None
  request_verified: bool = False
  closure_fingerprint_verified: bool = False
  upstream_handoff_verified: bool = False
  global_shock_curve_verified: bool = False
  supersonic_patch_verified: bool = False
  terminal_seam_verified: bool = False
  handoff_verified: bool = False
  control_section_verified: bool = False
  geometry_verified: bool = False
  pressure_lineage_verified: bool = False
  entropy_transport_verified: bool = False
  boundary_condition_verified: bool = False
  tangency_verified: bool = False
  reference_field_verified: bool = False
  mixed_regime_field_verified: bool = False
  conservative_euler_residuals_measured: bool = False
  conservative_euler_residuals_verified: bool = False
  residual_channel_coverage: Mapping[str, bool] = field(
    default_factory=lambda: MappingProxyType({})
  )
  residual_channel_validity: Mapping[str, bool] = field(
    default_factory=lambda: MappingProxyType({})
  )
  maximum_conservative_mass_residual: float | None = None
  maximum_conservative_streamwise_momentum_residual: float | None = None
  maximum_conservative_transverse_momentum_residual: float | None = None
  maximum_conservative_energy_residual: float | None = None
  maximum_conservative_euler_residual: float | None = None
  maximum_pressure_residual_Pa: float | None = None
  maximum_tangent_residual_rad: float | None = None
  maximum_entropy_residual: float | None = None
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  refinement_verified: bool = False
  external_validation_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  reference_measurement: MocMixedRegimeVariableEntropyFreeBoundaryMeasurement | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainMixedRegimeBoundaryMeasurementStatus'
      )
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainMixedRegimeBoundaryResult,
    ):
      raise TypeError(
        'candidate must be a MocReflectedDomainMixedRegimeBoundaryResult or None'
      )
    ####
    if self.reference_measurement is not None and not isinstance(
      self.reference_measurement,
      MocMixedRegimeVariableEntropyFreeBoundaryMeasurement,
    ):
      raise TypeError(
        'reference_measurement must be a '
        'MocMixedRegimeVariableEntropyFreeBoundaryMeasurement or None'
      )
    ####
    for name in (
      'request_verified',
      'closure_fingerprint_verified',
      'upstream_handoff_verified',
      'global_shock_curve_verified',
      'supersonic_patch_verified',
      'terminal_seam_verified',
      'handoff_verified',
      'control_section_verified',
      'geometry_verified',
      'pressure_lineage_verified',
      'entropy_transport_verified',
      'boundary_condition_verified',
      'tangency_verified',
      'reference_field_verified',
      'mixed_regime_field_verified',
      'conservative_euler_residuals_measured',
      'conservative_euler_residuals_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'refinement_verified',
      'external_validation_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'maximum_conservative_mass_residual',
      'maximum_conservative_streamwise_momentum_residual',
      'maximum_conservative_transverse_momentum_residual',
      'maximum_conservative_energy_residual',
      'maximum_conservative_euler_residual',
      'maximum_pressure_residual_Pa',
      'maximum_tangent_residual_rad',
      'maximum_entropy_residual',
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
    for name in ('residual_channel_coverage', 'residual_channel_validity'):
      values = dict(getattr(self, name))
      if any(
        not isinstance(key, str) or not isinstance(value, bool)
        for key, value in values.items()
      ):
        raise TypeError(f'{name} must map string channels to bool values')
      ####
      object.__setattr__(self, name, MappingProxyType(values))
    ####
    if self.production_claim_allowed or self.physical_closure_verified:
      raise ValueError(
        'mixed-regime boundary measurement cannot authorize physical or '
        'production claims'
      )
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.CONVERGED
    )
  ####

  @property
  def reference_verified(self) -> bool:
    """Whether the bound research reference passed every local audit."""

    return bool(
      self.converged
      and self.request_verified
      and self.closure_fingerprint_verified
      and self.upstream_handoff_verified
      and self.global_shock_curve_verified
      and self.supersonic_patch_verified
      and self.terminal_seam_verified
      and self.handoff_verified
      and self.control_section_verified
      and self.geometry_verified
      and self.pressure_lineage_verified
      and self.entropy_transport_verified
      and self.boundary_condition_verified
      and self.tangency_verified
      and self.reference_field_verified
      and self.conservative_euler_residuals_measured
      and self.conservative_euler_residuals_verified
      and not self.mixed_regime_field_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'reference_verified': self.reference_verified,
      'model': MIXED_REGIME_BOUNDARY_MODEL,
      'checks': {
        'request_verified': self.request_verified,
        'closure_fingerprint_verified': self.closure_fingerprint_verified,
        'upstream_handoff_verified': self.upstream_handoff_verified,
        'global_shock_curve_verified': self.global_shock_curve_verified,
        'supersonic_patch_verified': self.supersonic_patch_verified,
        'terminal_seam_verified': self.terminal_seam_verified,
        'handoff_verified': self.handoff_verified,
        'control_section_verified': self.control_section_verified,
        'geometry_verified': self.geometry_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'entropy_transport_verified': self.entropy_transport_verified,
        'boundary_condition_verified': self.boundary_condition_verified,
        'tangency_verified': self.tangency_verified,
        'reference_field_verified': self.reference_field_verified,
        'mixed_regime_field_verified': self.mixed_regime_field_verified,
        'conservative_euler_residuals_measured': (
          self.conservative_euler_residuals_measured
        ),
        'conservative_euler_residuals_verified': (
          self.conservative_euler_residuals_verified
        ),
      },
      'residual_channel_coverage': dict(self.residual_channel_coverage),
      'residual_channel_validity': dict(self.residual_channel_validity),
      'residuals': {
        'maximum_conservative_mass_residual': self.maximum_conservative_mass_residual,
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
        'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
        'maximum_tangent_residual_rad': self.maximum_tangent_residual_rad,
        'maximum_entropy_residual': self.maximum_entropy_residual,
      },
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'refinement_verified': self.refinement_verified,
      'external_validation_verified': self.external_validation_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate': (
        None
        if self.candidate is None or self.candidate.request is None
        else self.candidate.request.as_report()
      ),
      'reference_measurement': (
        None
        if self.reference_measurement is None
        else self.reference_measurement.as_report()
      ),
      'message': self.message,
      'claim_status': (
        'independent-global-mixed-regime-reference-measurement; '
        'canonical-reflected-2d-closure-and-production-chain-pending'
      ),
    }
  ####
####


def _mixed_regime_refinement_failure(
  status: MocReflectedDomainMixedRegimeBoundaryRefinementStatus,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement:
  return MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement(
    status=status,
    physical_closure_verified=False,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status=(
      'independent-global-to-mixed-regime-reference-refinement-evidence; '
      'canonical-2d-euler-free-boundary-and-external-validation-pending'
    ),
    message=message,
    **kwargs,
  )
####


def measure_reflected_domain_mixed_regime_boundary_refinement(
  cases: Sequence[MocReflectedDomainMixedRegimeBoundaryRefinementCase],
  *,
  geometry_tolerance_m: float = 1.0e-4,
  outlet_height_tolerance_m: float = 1.0e-4,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  residual_tolerance: float = 1.0e-7,
  continuity_tolerance: float = 0.25,
  entropy_transport_tolerance: float = 0.25,
) -> MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement:
  """Compare independently measured global-to-mixed-regime references.

  Each case may have a different global shock curve and derived terminal
  perimeter.  The source band and request-level reference parameters must
  remain fixed, while the global and downstream meshes grow with the declared
  resolution.  Residual magnitudes are retained as evidence, but are not
  required to be monotone because this mapped reference is not a converged
  two-dimensional Euler free-boundary solve.
  """

  for name, value in (
    ('geometry_tolerance_m', geometry_tolerance_m),
    ('outlet_height_tolerance_m', outlet_height_tolerance_m),
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
    ####
  ####
  try:
    items = tuple(cases)
  except TypeError:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  ####
  if len(items) < 2:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.INVALID_INPUT,
      'at least two mixed-regime refinement cases are required',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainMixedRegimeBoundaryRefinementCase,
    )
    for case in items
  ):
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.INVALID_INPUT,
      'refinement cases must contain '
      'MocReflectedDomainMixedRegimeBoundaryRefinementCase values',
    )
  ####
  resolutions = tuple(case.resolution for case in items)
  resolution_order_verified = all(
    right > left for left, right in zip(resolutions, resolutions[1:])
  )
  if not resolution_order_verified:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing from coarse to fine',
    )
  ####

  measurements = tuple(
    measure_reflected_domain_mixed_regime_boundary(
      case.result,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance_rad=tangent_tolerance_rad,
      residual_tolerance=residual_tolerance,
      continuity_tolerance=continuity_tolerance,
      entropy_transport_tolerance=entropy_transport_tolerance,
    )
    for case in items
  )
  results = tuple(case.result for case in items)
  closure_fingerprints = tuple(
    _mixed_regime_candidate_closure_fingerprint(result)
    for result in results
  )
  source_band_fingerprints = tuple(
    _mixed_regime_candidate_source_band_fingerprint(result)
    for result in results
  )
  ambient_pressure_fractions = tuple(
    _mixed_regime_candidate_ambient_fraction(result)
    for result in results
  )
  case_measurements_verified = all(
    measurement.reference_verified
    and measurement.status is (
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.CONVERGED
    )
    for measurement in measurements
  )
  conservative_euler_evidence_verified = all(
    measurement.conservative_euler_residuals_measured
    and measurement.conservative_euler_residuals_verified
    and all(measurement.residual_channel_coverage.values())
    and all(measurement.residual_channel_validity.values())
    for measurement in measurements
  )
  source_band_consistent = bool(
    all(source_band_fingerprints)
    and len(set(source_band_fingerprints)) == 1
  )
  closure_fingerprints_verified = bool(
    all(closure_fingerprints)
    and all(
      measurement.closure_fingerprint_verified
      and measurement.request_verified
      for measurement in measurements
    )
  )

  requests = tuple(result.request for result in results)
  request_parameters_consistent = False
  if all(request is not None for request in requests):
    typed_requests = tuple(
      request for request in requests if request is not None
    )
    first_request = typed_requests[0]
    typed_ambient_fractions = tuple(
      fraction
      for fraction in ambient_pressure_fractions
      if fraction is not None
    )

    def consistent_float(values: Sequence[float]) -> bool:
      reference = float(values[0])
      return all(
        abs(float(value) - reference)
        <= 1.0e-12 * max(1.0, abs(float(value)), abs(reference))
        for value in values[1:]
      )
    ####

    request_parameters_consistent = bool(
      all(request.source == first_request.source for request in typed_requests)
      and consistent_float(
        tuple(request.downstream_length_m for request in typed_requests)
      )
      and consistent_float(
        tuple(request.initial_outlet_height_m for request in typed_requests)
      )
      and consistent_float(
        tuple(request.control_section_x_offset_m for request in typed_requests)
      )
      and consistent_float(
        tuple(request.control_section_height_m for request in typed_requests)
      )
      and len({request.control_section_sample_count for request in typed_requests})
      == 1
      and len(typed_ambient_fractions) == len(typed_requests)
      and consistent_float(typed_ambient_fractions)
    )
  ####

  def global_shock_sample_count(
    result: MocReflectedDomainMixedRegimeBoundaryResult,
  ) -> int:
    closure = _mixed_regime_candidate_closure(result)
    global_euler = None if closure is None else closure.global_euler
    curve = None if global_euler is None else global_euler.shock_boundary
    return 0 if curve is None else len(curve.shock_points_m)
  ####

  global_shock_sample_counts = tuple(
    global_shock_sample_count(result) for result in results
  )
  reference_axial_station_counts = tuple(
    0 if result.reference is None else result.reference.axial_station_count
    for result in results
  )
  reference_transverse_station_counts = tuple(
    0 if result.reference is None else result.reference.transverse_station_count
    for result in results
  )
  node_counts = tuple(
    0 if result.reference is None else result.reference.node_count
    for result in results
  )
  cell_counts = tuple(
    0 if result.reference is None else result.reference.cell_count
    for result in results
  )
  global_shock_resolution_verified = all(
    count == resolution
    for count, resolution in zip(
      global_shock_sample_counts,
      resolutions,
      strict=True,
    )
  )
  mesh_resolution_verified = bool(
    global_shock_resolution_verified
    and all(
      right > left
      for left, right in zip(
        reference_axial_station_counts,
        reference_axial_station_counts[1:],
      )
    )
    and all(
      right >= left
      for left, right in zip(
        reference_transverse_station_counts,
        reference_transverse_station_counts[1:],
      )
    )
    and all(right > left for left, right in zip(node_counts, node_counts[1:]))
    and all(right > left for left, right in zip(cell_counts, cell_counts[1:]))
  )
  upstream_global_physical_closure_verified = all(
    closure is not None
    and closure.physical_closure_verified
    for closure in (
      _mixed_regime_candidate_closure(result) for result in results
    )
  )

  geometry_sample_fractions = (
    0.0,
    0.125,
    0.25,
    0.375,
    0.5,
    0.625,
    0.75,
    0.875,
    1.0,
  )
  sampled_heights = tuple(
    tuple(
      None
      if result.reference is None
      else _mixed_regime_reference_height_at_fraction(
        result.reference,
        fraction,
      )
      for fraction in geometry_sample_fractions
    )
    for result in results
  )
  if all(
    height is not None for sample in sampled_heights for height in sample
  ):
    free_boundary_shape_delta_residuals = tuple(
      max(
        abs(float(current) - float(previous))
        for previous, current in zip(
          sampled_heights[index - 1],
          sampled_heights[index],
          strict=True,
        )
      )
      for index in range(1, len(sampled_heights))
    )
  else:
    free_boundary_shape_delta_residuals = ()
  ####
  outlet_heights = tuple(
    None if result.reference is None else result.reference.outlet_height_m
    for result in results
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
  ####
  geometry_sensitivity_verified = bool(
    len(free_boundary_shape_delta_residuals) == len(items) - 1
    and all(
      residual <= float(geometry_tolerance_m)
      for residual in free_boundary_shape_delta_residuals
    )
  )
  outlet_height_stability_verified = bool(
    len(outlet_height_delta_residuals) == len(items) - 1
    and all(
      residual <= float(outlet_height_tolerance_m)
      for residual in outlet_height_delta_residuals
    )
  )
  refinement_convergence_verified = bool(
    case_measurements_verified
    and conservative_euler_evidence_verified
    and source_band_consistent
    and closure_fingerprints_verified
    and request_parameters_consistent
    and mesh_resolution_verified
    and geometry_sensitivity_verified
    and outlet_height_stability_verified
    and upstream_global_physical_closure_verified
  )
  fidelity_isolation_verified = all(
    result.mixed_regime_field_verified is False
    and result.physical_closure_verified is False
    and result.canonical_free_boundary_verified is False
    and result.canonical_euler_verified is False
    and result.external_validation_verified is False
    and result.downstream_boundary_closure_verified is False
    and result.chain_promotion_blocked
    and result.production_claim_allowed is False
    and measurement.chain_promotion_blocked
    and measurement.production_claim_allowed is False
    for result, measurement in zip(results, measurements, strict=True)
  )
  common = {
    'cases': items,
    'measurements': measurements,
    'closure_fingerprints': closure_fingerprints,
    'source_band_fingerprints': source_band_fingerprints,
    'ambient_pressure_fractions': ambient_pressure_fractions,
    'global_shock_sample_counts': global_shock_sample_counts,
    'reference_axial_station_counts': reference_axial_station_counts,
    'reference_transverse_station_counts': reference_transverse_station_counts,
    'node_counts': node_counts,
    'cell_counts': cell_counts,
    'outlet_heights_m': outlet_heights,
    'maximum_conservative_euler_residuals': tuple(
      measurement.maximum_conservative_euler_residual
      for measurement in measurements
    ),
    'resolution_order_verified': resolution_order_verified,
    'source_band_consistent': source_band_consistent,
    'closure_fingerprints_verified': closure_fingerprints_verified,
    'request_parameters_consistent': request_parameters_consistent,
    'case_measurements_verified': case_measurements_verified,
    'conservative_euler_evidence_verified': (
      conservative_euler_evidence_verified
    ),
    'mesh_resolution_verified': mesh_resolution_verified,
    'geometry_sensitivity_verified': geometry_sensitivity_verified,
    'outlet_height_stability_verified': outlet_height_stability_verified,
    'refinement_convergence_verified': refinement_convergence_verified,
    'upstream_global_physical_closure_verified': (
      upstream_global_physical_closure_verified
    ),
    'fidelity_isolation_verified': fidelity_isolation_verified,
    'geometry_sample_fractions': geometry_sample_fractions,
    'outlet_height_delta_residuals_m': outlet_height_delta_residuals,
    'free_boundary_shape_delta_residuals_m': (
      free_boundary_shape_delta_residuals
    ),
    'geometry_tolerance_m': float(geometry_tolerance_m),
    'outlet_height_tolerance_m': float(outlet_height_tolerance_m),
  }
  if not case_measurements_verified:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.CASE_FAILURE,
      'one or more mixed-regime references failed independent measurement',
      **common,
    )
  ####
  if not (
    source_band_consistent
    and closure_fingerprints_verified
    and request_parameters_consistent
    and mesh_resolution_verified
    and upstream_global_physical_closure_verified
  ):
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.CONSISTENCY_FAILURE,
      'refinement cases must retain one source band, valid closure bindings, '
      'fixed reference parameters, and growing global/downstream meshes',
      **common,
    )
  ####
  if not refinement_convergence_verified:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.SENSITIVITY_FAILURE,
      'mixed-regime reference geometry or outlet height exceeded the supplied '
      'stability tolerances',
      **common,
    )
  ####
  if not fidelity_isolation_verified:
    return _mixed_regime_refinement_failure(
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.FIDELITY_FAILURE,
      'mixed-regime refinement weakened its canonical or production stop',
      **common,
    )
  ####
  return MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement(
    status=MocReflectedDomainMixedRegimeBoundaryRefinementStatus.CONVERGED,
    claim_status=(
      'independent-global-to-mixed-regime-reference-refinement-evidence; '
      'geometry-and-output-sensitivity-only; canonical-2d-euler-free-boundary-'
      'and-external-validation-pending'
    ),
    message=(
      'independent global-to-mixed-regime reference measurements are stable '
      'across the declared ladder; the mapped scalar reference remains below '
      'canonical reflected 2-D closure and production-chain promotion'
    ),
    **common,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryRefinementRun:
  """Fresh global and mixed-regime reference executions plus their audit."""

  source_band: MocReflectedDomainAlternatingSourceResult
  requested_resolutions: tuple[int, ...]
  closures: tuple[MocReflectedDomainGlobalPhysicalClosureResult, ...]
  requests: tuple[MocReflectedDomainMixedRegimeBoundaryRequest | None, ...]
  cases: tuple[MocReflectedDomainMixedRegimeBoundaryRefinementCase, ...]
  measurement: MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement
  source_band_fingerprint: str
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool
  upstream_global_physical_closure_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    resolutions = tuple(self.requested_resolutions)
    if not resolutions:
      raise ValueError('requested_resolutions must not be empty')
    ####
    if any(
      isinstance(resolution, bool)
      or not isinstance(resolution, int)
      or resolution < 5
      for resolution in resolutions
    ):
      raise ValueError(
        'requested_resolutions must contain integers greater than or equal to 5'
      )
    ####
    closures = tuple(self.closures)
    requests = tuple(self.requests)
    cases = tuple(self.cases)
    if len(closures) != len(resolutions):
      raise ValueError('closures must match requested_resolutions')
    ####
    if len(requests) != len(resolutions):
      raise ValueError('requests must match requested_resolutions')
    ####
    if len(cases) != len(resolutions):
      raise ValueError('cases must match requested_resolutions')
    ####
    if any(
      not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult)
      for closure in closures
    ):
      raise TypeError(
        'closures must contain MocReflectedDomainGlobalPhysicalClosureResult values'
      )
    ####
    if any(
      request is not None
      and not isinstance(
        request,
        MocReflectedDomainMixedRegimeBoundaryRequest,
      )
      for request in requests
    ):
      raise TypeError(
        'requests must contain MocReflectedDomainMixedRegimeBoundaryRequest '
        'values or None'
      )
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainMixedRegimeBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocReflectedDomainMixedRegimeBoundaryRefinementCase values'
      )
    ####
    if tuple(case.resolution for case in cases) != resolutions:
      raise ValueError('case resolutions must match requested_resolutions')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement,
    ):
      raise TypeError(
        'measurement must be a '
        'MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement'
      )
    ####
    if tuple(self.measurement.cases) != cases:
      raise ValueError('measurement cases must match retained run cases')
    ####
    object.__setattr__(self, 'requested_resolutions', resolutions)
    object.__setattr__(self, 'closures', closures)
    object.__setattr__(self, 'requests', requests)
    object.__setattr__(self, 'cases', cases)
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError('configuration must contain (name, value) pairs')
    ####
    object.__setattr__(self, 'configuration', configuration)
    for name in ('source_band_fingerprint', 'configuration_fingerprint'):
      value = str(getattr(self, name))
      if not value:
        raise ValueError(f'{name} must be a non-empty string')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'upstream_global_physical_closure_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.measurement.local_consistency_verified
      and self.fresh_solver_invocation_verified
      and self.upstream_global_physical_closure_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return bool(
      self.closures
      and all(closure.chain_promotion_blocked for closure in self.closures)
      and all(case.result.chain_promotion_blocked for case in self.cases)
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.measurement.status.value,
      'operator_id': (
        MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_band_fingerprint': self.source_band_fingerprint,
      'configuration_fingerprint': self.configuration_fingerprint,
      'configuration': dict(self.configuration),
      'requested_resolutions': list(self.requested_resolutions),
      'closures': [
        {
          'resolution': resolution,
          'status': closure.status.value,
          'converged': closure.converged,
          'physical_closure_verified': closure.physical_closure_verified,
          'global_euler_retained': closure.global_euler is not None,
          'downstream_boundary_model': closure.downstream_boundary_model,
          'downstream_boundary_closure_verified': (
            closure.downstream_boundary_closure_verified
          ),
          'chain_promotion_blocked': closure.chain_promotion_blocked,
          'production_claim_allowed': closure.production_claim_allowed,
        }
        for resolution, closure in zip(
          self.requested_resolutions,
          self.closures,
          strict=True,
        )
      ],
      'requests_retained': [request is not None for request in self.requests],
      'cases': [
        {
          'resolution': case.resolution,
          'solver_status': case.result.status.value,
        }
        for case in self.cases
      ],
      'measurement': self.measurement.as_report(),
      'checks': {
        'fresh_solver_invocation_verified': (
          self.fresh_solver_invocation_verified
        ),
        'upstream_global_physical_closure_verified': (
          self.upstream_global_physical_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'claim_status': (
        'fresh-global-to-mixed-regime-reference-resolution-run; '
        'mapped-scalar-research-only'
      ),
      'message': self.message,
    }
  ####
####


def _mixed_regime_failed_candidate(
  status: MocReflectedDomainMixedRegimeBoundaryStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None,
) -> MocReflectedDomainMixedRegimeBoundaryResult:
  return MocReflectedDomainMixedRegimeBoundaryResult(
    status=status,
    request=request,
    closure=closure if request is None else request.closure,
    perimeter_request=(None if request is None else request.perimeter_request),
    entropy_handoff=(None if request is None else request.entropy_handoff),
    control_section=(None if request is None else request.control_section),
    reference=None,
    message=message,
  )
####


def run_reflected_domain_mixed_regime_boundary_refinement(
  source_band: MocReflectedDomainAlternatingSourceResult,
  resolutions: Sequence[int],
  *,
  outer_source_indices: Sequence[int] | None = None,
  target_centerline_indices: Sequence[int] | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  compression_envelope_skews: Sequence[float] = (-0.75, 0.0, 0.75),
  closure_tolerance_m: float = 1.0e-6,
  incoming_handoff: Sequence[Any] | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  reference_ambient_fraction: float = 0.98,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float | None = None,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  reference_axial_station_count: int | None = None,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  euler_reconciliation_shock_angle_tolerance_rad: float = 1.0e-8,
  euler_reconciliation_residual_tolerance: float = 1.0e-8,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  maximum_attempts: int = 64,
  geometry_tolerance_m: float = 1.0e-4,
  outlet_height_tolerance_m: float = 1.0e-4,
  audit_state_tolerance: float = 1.0e-8,
  audit_tangent_tolerance_rad: float = 2.0e-2,
  audit_residual_tolerance: float = 1.0e-7,
  audit_continuity_tolerance: float = 0.25,
  audit_entropy_transport_tolerance: float = 0.25,
) -> MocReflectedDomainMixedRegimeBoundaryRefinementRun:
  """Run fresh global closures and mixed-regime reference solves.

  ``resolutions`` controls the global shock sample count.  Unless explicitly
  overridden, the scalar downstream reference uses the same axial station
  count, so the reported ladder spans both retained meshes.  The ambient
  pressure is a fixed fraction of each case's terminal total pressure; this
  is an explicit reference condition and is not the mission ambient model.
  """

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  ####
  try:
    requested_resolutions = tuple(resolutions)
  except TypeError as error:
    raise ValueError(
      'resolutions must be an iterable of integers greater than or equal to 5'
    ) from error
  ####
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
  ####
  if any(
    isinstance(resolution, bool)
    or not isinstance(resolution, int)
    or resolution < 5
    for resolution in requested_resolutions
  ):
    raise ValueError(
      'resolutions must contain integers greater than or equal to 5'
    )
  ####
  fraction = float(reference_ambient_fraction)
  if not isfinite(fraction) or not 0.0 < fraction < 1.0:
    raise ValueError('reference_ambient_fraction must lie strictly between 0 and 1')
  ####
  if (
    reference_axial_station_count is not None
    and (
      isinstance(reference_axial_station_count, bool)
      or not isinstance(reference_axial_station_count, int)
      or reference_axial_station_count < 5
    )
  ):
    raise ValueError(
      'reference_axial_station_count must be an integer greater than or equal to 5'
    )
  ####

  def optional_tuple(
    value: Sequence[Any] | None,
    name: str,
  ) -> tuple[Any, ...] | None:
    if value is None:
      return None
    ####
    try:
      return tuple(value)
    except TypeError as error:
      raise ValueError(f'{name} must be an iterable or None') from error
    ####
  ####

  resolved_outer_indices = optional_tuple(
    outer_source_indices,
    'outer_source_indices',
  )
  resolved_centerline_indices = optional_tuple(
    target_centerline_indices,
    'target_centerline_indices',
  )
  resolved_skews = optional_tuple(
    compression_envelope_skews,
    'compression_envelope_skews',
  )
  resolved_handoff = optional_tuple(incoming_handoff, 'incoming_handoff')
  if resolved_handoff is not None and any(
    not isinstance(sample, MocChainBoundarySample)
    for sample in resolved_handoff
  ):
    raise TypeError(
      'incoming_handoff must contain MocChainBoundarySample values'
    )
  ####
  resolved_source_handoff = (
    source_band.incoming_handoff
    if resolved_handoff is None
    else resolved_handoff
  )
  source_fingerprint = _mixed_regime_source_band_fingerprint(source_band)
  configuration_payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID
    ),
    'source_band_fingerprint': source_fingerprint,
    'requested_resolutions': list(requested_resolutions),
    'outer_source_indices': (
      None
      if resolved_outer_indices is None
      else list(resolved_outer_indices)
    ),
    'target_centerline_indices': (
      None
      if resolved_centerline_indices is None
      else list(resolved_centerline_indices)
    ),
    'compression_amplitude_lower_rad': compression_amplitude_lower_rad,
    'compression_amplitude_upper_rad': compression_amplitude_upper_rad,
    'compression_envelope_skews': (
      None if resolved_skews is None else list(resolved_skews)
    ),
    'closure_tolerance_m': closure_tolerance_m,
    'incoming_handoff': repr(resolved_source_handoff),
    'branch': getattr(branch, 'value', str(branch)),
    'reference_ambient_fraction': fraction,
    'downstream_length_m': downstream_length_m,
    'initial_outlet_height_m': initial_outlet_height_m,
    'control_section_x_offset_m': control_section_x_offset_m,
    'control_section_height_m': control_section_height_m,
    'control_section_sample_count': control_section_sample_count,
    'reference_axial_station_count': reference_axial_station_count,
    'position_tolerance_m': position_tolerance_m,
    'invariant_tolerance': invariant_tolerance,
    'attachment_pressure_tolerance': attachment_pressure_tolerance,
    'pressure_tolerance': pressure_tolerance,
    'tangent_tolerance': tangent_tolerance,
    'shock_angle_tolerance_rad': shock_angle_tolerance_rad,
    'euler_reconciliation_shock_angle_tolerance_rad': (
      euler_reconciliation_shock_angle_tolerance_rad
    ),
    'euler_reconciliation_residual_tolerance': (
      euler_reconciliation_residual_tolerance
    ),
    'maximum_segment_iterations': maximum_segment_iterations,
    'maximum_boundary_iterations': maximum_boundary_iterations,
    'maximum_shooting_iterations': maximum_shooting_iterations,
    'maximum_bracket_scan_samples': maximum_bracket_scan_samples,
    'maximum_attempts': maximum_attempts,
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _mixed_regime_refinement_fingerprint(
    configuration_payload
  )

  closures: list[MocReflectedDomainGlobalPhysicalClosureResult] = []
  requests: list[MocReflectedDomainMixedRegimeBoundaryRequest | None] = []
  candidates: list[MocReflectedDomainMixedRegimeBoundaryResult] = []
  cases: list[MocReflectedDomainMixedRegimeBoundaryRefinementCase] = []
  for resolution in requested_resolutions:
    try:
      closure = solve_reflected_domain_global_physical_closure(
        source_band,
        outer_source_indices=resolved_outer_indices,
        target_centerline_indices=resolved_centerline_indices,
        compression_amplitude_lower_rad=compression_amplitude_lower_rad,
        compression_amplitude_upper_rad=compression_amplitude_upper_rad,
        compression_envelope_skews=(
          () if resolved_skews is None else resolved_skews
        ),
        closure_tolerance_m=closure_tolerance_m,
        incoming_handoff=resolved_handoff,
        sample_count=resolution,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        euler_reconciliation_shock_angle_tolerance_rad=(
          euler_reconciliation_shock_angle_tolerance_rad
        ),
        euler_reconciliation_residual_tolerance=(
          euler_reconciliation_residual_tolerance
        ),
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        maximum_bracket_scan_samples=maximum_bracket_scan_samples,
        maximum_attempts=maximum_attempts,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      closure = MocReflectedDomainGlobalPhysicalClosureResult(
        status=MocReflectedDomainGlobalPhysicalClosureStatus.GLOBAL_REMESH_FAILURE,
        source_band=source_band,
        global_remesh=None,
        global_euler=None,
        message=f'fresh global physical closure raised: {error}',
      )
    ####
    closures.append(closure)
    request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None
    if not closure.physical_closure_verified:
      candidate = _mixed_regime_failed_candidate(
        MocReflectedDomainMixedRegimeBoundaryStatus.UPSTREAM_CLOSURE_FAILURE,
        'fresh global closure did not satisfy the local physical-closure gate',
        closure=closure,
      )
    else:
      try:
        request_template = build_reflected_domain_mixed_regime_boundary_request(
          closure,
          downstream_length_m=downstream_length_m,
          initial_outlet_height_m=initial_outlet_height_m,
          control_section_x_offset_m=control_section_x_offset_m,
          control_section_height_m=control_section_height_m,
          control_section_sample_count=control_section_sample_count,
          axial_station_count=(
            resolution
            if reference_axial_station_count is None
            else reference_axial_station_count
          ),
        )
        terminal_reference_pressure = (
          request_template.entropy_handoff.samples[0]
          .downstream_total_pressure_Pa
        )
        request = replace(
          request_template,
          ambient_pressure_Pa=(
            fraction * float(terminal_reference_pressure)
          ),
        )
        candidate = solve_reflected_domain_mixed_regime_boundary(request)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        candidate = _mixed_regime_failed_candidate(
          MocReflectedDomainMixedRegimeBoundaryStatus.REQUEST_SEAM_FAILURE,
          f'fresh mixed-regime reference request raised: {error}',
          closure=closure,
          request=request,
        )
      ####
    ####
    requests.append(request)
    candidates.append(candidate)
    cases.append(
      MocReflectedDomainMixedRegimeBoundaryRefinementCase(
        resolution=resolution,
        result=candidate,
      )
    )
  ####
  measurement = measure_reflected_domain_mixed_regime_boundary_refinement(
    tuple(cases),
    geometry_tolerance_m=geometry_tolerance_m,
    outlet_height_tolerance_m=outlet_height_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=audit_state_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance_rad=audit_tangent_tolerance_rad,
    residual_tolerance=audit_residual_tolerance,
    continuity_tolerance=audit_continuity_tolerance,
    entropy_transport_tolerance=audit_entropy_transport_tolerance,
  )
  upstream_global_physical_closure_verified = bool(
    closures and all(closure.physical_closure_verified for closure in closures)
  )
  fidelity_isolation_verified = bool(
    candidates
    and all(
      candidate.chain_promotion_blocked
      and not candidate.production_claim_allowed
      for candidate in candidates
    )
    and all(
      closure.chain_promotion_blocked
      and not closure.production_claim_allowed
      for closure in closures
    )
  )
  return MocReflectedDomainMixedRegimeBoundaryRefinementRun(
    source_band=source_band,
    requested_resolutions=requested_resolutions,
    closures=tuple(closures),
    requests=tuple(requests),
    cases=tuple(cases),
    measurement=measurement,
    source_band_fingerprint=source_fingerprint,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(closures) == len(requested_resolutions)
    ),
    upstream_global_physical_closure_verified=(
      upstream_global_physical_closure_verified
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global-to-mixed-regime reference ladder completed; independent '
      'evidence remains below canonical reflected 2-D closure and external '
      'promotion gates'
    ),
  )
####


def _measurement_failure(
  status: MocReflectedDomainMixedRegimeBoundaryMeasurementStatus,
  message: str,
  *,
  candidate: MocReflectedDomainMixedRegimeBoundaryResult | None = None,
  reference_measurement: MocMixedRegimeVariableEntropyFreeBoundaryMeasurement | None = None,
  **values: Any,
) -> MocReflectedDomainMixedRegimeBoundaryMeasurement:
  return MocReflectedDomainMixedRegimeBoundaryMeasurement(
    status=status,
    candidate=candidate,
    reference_measurement=reference_measurement,
    message=message,
    **values,
  )
####


def _close(actual: float, expected: float, tolerance: float) -> bool:
  return abs(float(actual) - float(expected)) <= tolerance * max(
    1.0,
    abs(float(actual)),
    abs(float(expected)),
  )
####


def _terminal_scalars(
  terminal: MocNormalShockTerminalResult,
) -> tuple[float, float, float, float, float, float, float] | None:
  upstream = terminal.upstream_state
  values = (
    terminal.upstream_pressure_Pa,
    terminal.downstream_mach,
    terminal.downstream_pressure_Pa,
    terminal.upstream_total_pressure_Pa,
    terminal.downstream_total_pressure_Pa,
    terminal.static_pressure_ratio,
    terminal.total_pressure_ratio,
  )
  if not isinstance(upstream, CharacteristicState) or any(
    value is None for value in values
  ):
    return None
  ####
  assert all(value is not None for value in values)
  return tuple(float(value) for value in values)  # type: ignore[return-value]
####


def _terminal_seam_matches_global_curve(
  terminal: MocNormalShockTerminalResult,
  curve: MocEulerShockBoundaryCurveResult,
  *,
  tolerance: float,
) -> bool:
  if not isinstance(terminal, MocNormalShockTerminalResult):
    return False
  ####
  if not curve.shock_points_m or not curve.downstream_states:
    return False
  ####
  index = len(curve.shock_points_m) - 1
  upstream = curve.downstream_states[index]
  pressure = curve.downstream_static_pressure_Pa[index]
  values = _terminal_scalars(terminal)
  if values is None or terminal.shock_point_m is None:
    return False
  ####
  if terminal.upstream_state != upstream or terminal.upstream_pressure_Pa is None:
    return False
  ####
  if terminal.shock_point_m != curve.shock_points_m[index]:
    return False
  ####
  gamma = upstream.gamma
  mach = upstream.mach
  static_ratio = 1.0 + (2.0 * gamma / (gamma + 1.0)) * (mach**2 - 1.0)
  downstream_mach = sqrt(
    (1.0 + 0.5 * (gamma - 1.0) * mach**2)
    / (gamma * mach**2 - 0.5 * (gamma - 1.0))
  )
  downstream_pressure = pressure * static_ratio
  total_ratio = (
    ((gamma + 1.0) * mach**2 / ((gamma - 1.0) * mach**2 + 2.0))
    ** (gamma / (gamma - 1.0))
    * ((gamma + 1.0) / (2.0 * gamma * mach**2 - (gamma - 1.0)))
    ** (1.0 / (gamma - 1.0))
  )
  upstream_total = pressure * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (gamma / (gamma - 1.0))
  downstream_total = downstream_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * downstream_mach * downstream_mach
  ) ** (gamma / (gamma - 1.0))
  expected = (
    pressure,
    downstream_mach,
    downstream_pressure,
    upstream_total,
    downstream_total,
    static_ratio,
    total_ratio,
  )
  return bool(
    terminal.converged
    and terminal.subsonic
    and _close(values[0], expected[0], tolerance)
    and _close(values[1], expected[1], tolerance)
    and _close(values[2], expected[2], tolerance)
    and _close(values[3], expected[3], tolerance)
    and _close(values[4], expected[4], tolerance)
    and _close(values[5], expected[5], tolerance)
    and _close(values[6], expected[6], tolerance)
    and _close(
      float(terminal.downstream_flow_angle_rad or 0.0),
      upstream.theta_rad,
      tolerance,
    )
  )
####


def _patch_matches_global_curve(
  patch: tuple[MocPostShockBoundaryState, ...],
  curve: MocEulerShockBoundaryCurveResult,
  *,
  tolerance: float,
) -> bool:
  if len(curve.shock_points_m) != len(curve.downstream_states):
    return False
  ####
  expected: list[MocPostShockBoundaryState] = []
  terminal_index = len(curve.shock_points_m) - 1
  for index in range(terminal_index):
    upstream_pressure = curve.upstream_total_pressure_Pa[index]
    downstream_pressure = curve.downstream_total_pressure_Pa[index]
    if downstream_pressure >= upstream_pressure - tolerance * max(
      1.0,
      abs(upstream_pressure),
      abs(downstream_pressure),
    ):
      continue
    ####
    expected.append(
      MocPostShockBoundaryState(
        point_m=curve.shock_points_m[index],
        state=curve.downstream_states[index],
        upstream_total_pressure_Pa=upstream_pressure,
        downstream_total_pressure_Pa=downstream_pressure,
      )
    )
  ####
  return tuple(expected) == patch and bool(patch) and all(
    sample.state.mach > 1.0 for sample in patch
  )
####


def measure_reflected_domain_mixed_regime_boundary(
  candidate: MocReflectedDomainMixedRegimeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance_rad: float = 2.0e-2,
  residual_tolerance: float = 1.0e-7,
  continuity_tolerance: float = 0.25,
  entropy_transport_tolerance: float = 0.25,
) -> MocReflectedDomainMixedRegimeBoundaryMeasurement:
  """Independently measure the bound research-only mixed-regime result."""

  if not isinstance(
    candidate,
    MocReflectedDomainMixedRegimeBoundaryResult,
  ):
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.INVALID_INPUT,
      'candidate must be a MocReflectedDomainMixedRegimeBoundaryResult',
    )
  ####
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
    ####
  ####
  request = candidate.request
  closure = candidate.closure
  if not isinstance(request, MocReflectedDomainMixedRegimeBoundaryRequest):
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.REQUEST_FAILURE,
      'candidate does not retain a typed mixed-regime boundary request',
      candidate=candidate,
    )
  ####
  request_verified = bool(
    closure is request.closure
    and candidate.perimeter_request == request.perimeter_request
    and candidate.entropy_handoff == request.entropy_handoff
    and candidate.control_section == request.control_section
  )
  closure_fingerprint_verified = False
  upstream_handoff_verified = False
  if closure is not None:
    try:
      closure_fingerprint_verified = request.closure_fingerprint == (
        moc_reflected_domain_global_physical_closure_fingerprint(closure)
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      closure_fingerprint_verified = False
    ####
    upstream_handoff_verified = bool(
      request.upstream_handoff == closure.incoming_handoff
      and request.upstream_handoff
    )
  ####
  if not request_verified or not closure_fingerprint_verified:
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.REQUEST_FAILURE,
      'candidate request, closure identity, or retained typed seams do not match',
      candidate=candidate,
      request_verified=request_verified,
      closure_fingerprint_verified=closure_fingerprint_verified,
      upstream_handoff_verified=upstream_handoff_verified,
    )
  ####
  if closure is None or not closure.physical_closure_verified:
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.UPSTREAM_FAILURE,
      'candidate closure is not a locally physically verified global closure',
      candidate=candidate,
      request_verified=True,
      closure_fingerprint_verified=True,
      upstream_handoff_verified=upstream_handoff_verified,
    )
  ####
  global_euler = closure.global_euler
  curve = None if global_euler is None else global_euler.shock_boundary
  global_shock_curve_verified = bool(
    global_euler is not None
    and global_euler.converged
    and isinstance(curve, MocEulerShockBoundaryCurveResult)
    and curve.converged
  )
  if not global_shock_curve_verified or curve is None:
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.UPSTREAM_FAILURE,
      'closure does not retain a converged global Euler shock curve',
      candidate=candidate,
      request_verified=True,
      closure_fingerprint_verified=True,
      upstream_handoff_verified=upstream_handoff_verified,
      global_shock_curve_verified=False,
    )
  ####
  perimeter_request = request.perimeter_request
  patch_verified = _patch_matches_global_curve(
    perimeter_request.supersonic_patch,
    curve,
    # The builder removes only zero-strength endpoint samples.  The audit's
    # broader pressure tolerance is reserved for residual comparisons and
    # must not silently remove weak but lossy interior samples.
    tolerance=1.0e-12,
  )
  terminal = perimeter_request.terminal
  terminal_seam_verified = bool(
    isinstance(terminal, MocNormalShockTerminalResult)
    and _terminal_seam_matches_global_curve(
      terminal,
      curve,
      tolerance=state_tolerance,
    )
  )
  if not patch_verified or not terminal_seam_verified:
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.TERMINAL_FAILURE,
      'candidate terminal or supersonic patch is not reproduced from the '
      'global Euler shock curve',
      candidate=candidate,
      request_verified=True,
      closure_fingerprint_verified=True,
      upstream_handoff_verified=upstream_handoff_verified,
      global_shock_curve_verified=True,
      supersonic_patch_verified=patch_verified,
      terminal_seam_verified=terminal_seam_verified,
    )
  ####
  reference = candidate.reference
  if reference is None:
    return _measurement_failure(
      MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.FIELD_FAILURE,
      'candidate does not retain its solved variable-entropy reference',
      candidate=candidate,
      request_verified=True,
      closure_fingerprint_verified=True,
      upstream_handoff_verified=upstream_handoff_verified,
      global_shock_curve_verified=True,
      supersonic_patch_verified=True,
      terminal_seam_verified=True,
    )
  ####
  reference_measurement = measure_mixed_regime_variable_entropy_free_boundary(
    perimeter_request,
    request.entropy_handoff,
    request.control_section,
    reference,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance_rad=tangent_tolerance_rad,
    residual_tolerance=residual_tolerance,
    continuity_tolerance=continuity_tolerance,
    entropy_transport_tolerance=entropy_transport_tolerance,
  )
  handoff_verified = bool(
    reference_measurement.handoff_verified
    and reference.handoff == request.entropy_handoff
    and request.entropy_handoff.request == perimeter_request
  )
  control_section_verified = bool(
    reference_measurement.control_section_verified
    and reference.control_section == request.control_section
  )
  reference_field_verified = bool(reference_measurement.reference_verified)
  geometry_verified = bool(
    reference_measurement.field_boundary_verified
    and reference_measurement.field_topology_verified
  )
  pressure_lineage_verified = bool(
    reference_measurement.source_streamline_mapping_verified
    and reference_measurement.entropy_transport_verified
  )
  entropy_transport_verified = bool(reference_measurement.entropy_transport_verified)
  boundary_condition_verified = bool(
    reference_measurement.free_boundary_condition_verified
  )
  tangency_verified = boundary_condition_verified
  residual_attributes = {
    'mass': 'maximum_conservative_mass_residual',
    'streamwise_momentum': 'maximum_conservative_streamwise_momentum_residual',
    'transverse_momentum': 'maximum_conservative_transverse_momentum_residual',
    'energy': 'maximum_conservative_energy_residual',
    'euler': 'maximum_conservative_euler_residual',
  }
  coverage = {
    name: bool(
      reference.field is not None
      and reference.field.cells
      and getattr(reference_measurement, attribute) is not None
    )
    for name, attribute in residual_attributes.items()
  }
  validity = {
    name: bool(
      coverage[name]
      and isfinite(float(getattr(reference_measurement, attribute)))
      and float(getattr(reference_measurement, attribute)) >= 0.0
    )
    for name, attribute in residual_attributes.items()
  }
  conservative_measured = bool(
    reference.conservative_euler_residuals_measured
    and all(coverage.values())
  )
  conservative_verified = bool(
    reference_measurement.conservative_euler_residuals_verified
    and all(validity.values())
  )
  common = {
    'candidate': candidate,
    'reference_measurement': reference_measurement,
    'request_verified': True,
    'closure_fingerprint_verified': True,
    'upstream_handoff_verified': upstream_handoff_verified,
    'global_shock_curve_verified': True,
    'supersonic_patch_verified': patch_verified,
    'terminal_seam_verified': terminal_seam_verified,
    'handoff_verified': handoff_verified,
    'control_section_verified': control_section_verified,
    'geometry_verified': geometry_verified,
    'pressure_lineage_verified': pressure_lineage_verified,
    'entropy_transport_verified': entropy_transport_verified,
    'boundary_condition_verified': boundary_condition_verified,
    'tangency_verified': tangency_verified,
    'reference_field_verified': reference_field_verified,
    'mixed_regime_field_verified': False,
    'conservative_euler_residuals_measured': conservative_measured,
    'conservative_euler_residuals_verified': conservative_verified,
    'residual_channel_coverage': coverage,
    'residual_channel_validity': validity,
    'maximum_conservative_mass_residual': reference_measurement.maximum_conservative_mass_residual,
    'maximum_conservative_streamwise_momentum_residual': reference_measurement.maximum_conservative_streamwise_momentum_residual,
    'maximum_conservative_transverse_momentum_residual': reference_measurement.maximum_conservative_transverse_momentum_residual,
    'maximum_conservative_energy_residual': reference_measurement.maximum_conservative_energy_residual,
    'maximum_conservative_euler_residual': reference_measurement.maximum_conservative_euler_residual,
    'maximum_pressure_residual_Pa': reference_measurement.maximum_free_boundary_pressure_residual_Pa,
    'maximum_tangent_residual_rad': reference_measurement.maximum_free_boundary_tangent_residual_rad,
    'maximum_entropy_residual': reference_measurement.maximum_entropy_advection_residual,
  }
  if not handoff_verified:
    status = MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.HANDOFF_FAILURE
    message = 'independent entropy handoff measurement did not pass'
  elif not control_section_verified:
    status = MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.CONTROL_SECTION_FAILURE
    message = 'independent control-section measurement did not pass'
  elif not reference_field_verified:
    status = MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.FIELD_FAILURE
    message = (
      'independent variable-entropy field measurement did not pass: '
      f'{reference_measurement.message}'
    )
  elif not conservative_measured or not conservative_verified:
    status = MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.RESIDUAL_FAILURE
    message = 'independent conservative-Euler residual channels are incomplete'
  else:
    status = MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.CONVERGED
    message = (
      'independent global-shock, terminal, entropy, control-section, '
      'boundary, and conservative-Euler residual measurements passed; the '
      'scalar reference remains below canonical reflected 2-D closure'
    )
  ####
  return MocReflectedDomainMixedRegimeBoundaryMeasurement(
    status=status,
    message=message,
    **common,
  )
####


def _mixed_regime_refinement_fingerprint(payload: Any) -> str:
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _mixed_regime_source_band_fingerprint(
  source_band: MocReflectedDomainAlternatingSourceResult,
) -> str:
  try:
    report = source_band.as_report()
  except (AttributeError, TypeError, ValueError):
    report = repr(source_band)
  ####
  return _mixed_regime_refinement_fingerprint(report)
####


def _mixed_regime_candidate_closure(
  candidate: MocReflectedDomainMixedRegimeBoundaryResult,
) -> MocReflectedDomainGlobalPhysicalClosureResult | None:
  if candidate.closure is not None:
    return candidate.closure
  ####
  request = candidate.request
  return None if request is None else request.closure
####


def _mixed_regime_candidate_source_band_fingerprint(
  candidate: MocReflectedDomainMixedRegimeBoundaryResult,
) -> str:
  closure = _mixed_regime_candidate_closure(candidate)
  source_band = None if closure is None else closure.source_band
  if source_band is None:
    return ''
  ####
  return _mixed_regime_source_band_fingerprint(source_band)
####


def _mixed_regime_candidate_closure_fingerprint(
  candidate: MocReflectedDomainMixedRegimeBoundaryResult,
) -> str:
  request = candidate.request
  if request is None:
    return ''
  ####
  try:
    expected = moc_reflected_domain_global_physical_closure_fingerprint(
      request.closure
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return ''
  ####
  return request.closure_fingerprint if request.closure_fingerprint == expected else ''
####


def _mixed_regime_candidate_ambient_fraction(
  candidate: MocReflectedDomainMixedRegimeBoundaryResult,
) -> float | None:
  request = candidate.request
  if request is None or not request.entropy_handoff.samples:
    return None
  ####
  reference_pressure = request.entropy_handoff.samples[0].downstream_total_pressure_Pa
  if not isfinite(float(reference_pressure)) or float(reference_pressure) <= 0.0:
    return None
  ####
  fraction = float(request.ambient_pressure_Pa) / float(reference_pressure)
  return fraction if isfinite(fraction) and fraction > 0.0 else None
####


def _mixed_regime_reference_height_at_fraction(
  result: MocMixedRegimeVariableEntropyFreeBoundaryResult,
  fraction: float,
  *,
  start_index: int = 2,
) -> float | None:
  heights = tuple(result.free_boundary_heights_m)
  if (
    len(heights) < 2
    or start_index < 0
    or start_index >= len(heights) - 1
    or not 0.0 <= float(fraction) <= 1.0
  ):
    return None
  ####
  comparable_heights = heights[start_index:]
  if any(
    not isfinite(float(height)) or float(height) <= 0.0
    for height in comparable_heights
  ):
    return None
  ####
  location = float(fraction) * (len(comparable_heights) - 1)
  lower = int(location)
  upper = min(lower + 1, len(comparable_heights) - 1)
  weight = location - lower
  return (
    (1.0 - weight) * float(comparable_heights[lower])
    + weight * float(comparable_heights[upper])
  )
####


class MocReflectedDomainMixedRegimeBoundaryRefinementStatus(str, Enum):
  """Outcome of the independent global-to-mixed-regime ladder audit."""

  CONVERGED = 'converged-global-mixed-regime-boundary-refinement'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'mixed-regime-refinement-resolution-failure'
  CASE_FAILURE = 'mixed-regime-refinement-case-failure'
  CONSISTENCY_FAILURE = 'mixed-regime-refinement-consistency-failure'
  SENSITIVITY_FAILURE = 'mixed-regime-refinement-sensitivity-failure'
  FIDELITY_FAILURE = 'mixed-regime-refinement-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryRefinementCase:
  """One solver-owned mixed-regime reference at a global resolution."""

  resolution: int
  result: MocReflectedDomainMixedRegimeBoundaryResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 5
    ):
      raise ValueError('resolution must be an integer greater than or equal to 5')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainMixedRegimeBoundaryResult,
    ):
      raise TypeError(
        'result must be a MocReflectedDomainMixedRegimeBoundaryResult'
      )
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryRefinementMeasurement:
  """Independent resolution evidence for the mapped mixed-regime reference.

  The global closure and the downstream scalar reference are both remeasured
  at every declared resolution.  The ladder may establish local sensitivity
  evidence, but it cannot satisfy the missing coupled two-dimensional Euler
  free-boundary law or promote a shock-cell chain.
  """

  status: MocReflectedDomainMixedRegimeBoundaryRefinementStatus
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_REFINEMENT_OPERATOR_ID
  )
  cases: tuple[MocReflectedDomainMixedRegimeBoundaryRefinementCase, ...] = ()
  measurements: tuple[MocReflectedDomainMixedRegimeBoundaryMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  closure_fingerprints: tuple[str, ...] = ()
  source_band_fingerprints: tuple[str, ...] = ()
  ambient_pressure_fractions: tuple[float | None, ...] = ()
  global_shock_sample_counts: tuple[int, ...] = ()
  reference_axial_station_counts: tuple[int, ...] = ()
  reference_transverse_station_counts: tuple[int, ...] = ()
  node_counts: tuple[int, ...] = ()
  cell_counts: tuple[int, ...] = ()
  outlet_heights_m: tuple[float | None, ...] = ()
  maximum_conservative_euler_residuals: tuple[float | None, ...] = ()
  resolution_order_verified: bool = False
  source_band_consistent: bool = False
  closure_fingerprints_verified: bool = False
  request_parameters_consistent: bool = False
  case_measurements_verified: bool = False
  conservative_euler_evidence_verified: bool = False
  mesh_resolution_verified: bool = False
  geometry_sensitivity_verified: bool = False
  outlet_height_stability_verified: bool = False
  refinement_convergence_verified: bool = False
  upstream_global_physical_closure_verified: bool = False
  physical_closure_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  external_validation_verified: bool = False
  fidelity_isolation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  geometry_sample_fractions: tuple[float, ...] = ()
  outlet_height_delta_residuals_m: tuple[float, ...] = ()
  free_boundary_shape_delta_residuals_m: tuple[float, ...] = ()
  geometry_tolerance_m: float = 1.0e-4
  outlet_height_tolerance_m: float = 1.0e-4
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainMixedRegimeBoundaryRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    measurements = tuple(self.measurements)
    if len(cases) != len(measurements):
      raise ValueError('cases and measurements must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainMixedRegimeBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocReflectedDomainMixedRegimeBoundaryRefinementCase values'
      )
    ####
    if any(
      not isinstance(
        measurement,
        MocReflectedDomainMixedRegimeBoundaryMeasurement,
      )
      for measurement in measurements
    ):
      raise TypeError(
        'measurements must contain '
        'MocReflectedDomainMixedRegimeBoundaryMeasurement values'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'measurements', measurements)
    resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != resolutions:
      raise ValueError('resolutions must match the supplied cases')
    ####
    object.__setattr__(self, 'resolutions', resolutions)

    derived_closure_fingerprints = tuple(
      _mixed_regime_candidate_closure_fingerprint(case.result)
      for case in cases
    )
    derived_source_band_fingerprints = tuple(
      _mixed_regime_candidate_source_band_fingerprint(case.result)
      for case in cases
    )
    derived_ambient_fractions = tuple(
      _mixed_regime_candidate_ambient_fraction(case.result)
      for case in cases
    )
    object.__setattr__(
      self,
      'closure_fingerprints',
      derived_closure_fingerprints,
    )
    object.__setattr__(
      self,
      'source_band_fingerprints',
      derived_source_band_fingerprints,
    )
    object.__setattr__(
      self,
      'ambient_pressure_fractions',
      derived_ambient_fractions,
    )

    def closure_curve_count(
      case: MocReflectedDomainMixedRegimeBoundaryRefinementCase,
    ) -> int:
      closure = _mixed_regime_candidate_closure(case.result)
      global_euler = None if closure is None else closure.global_euler
      curve = None if global_euler is None else global_euler.shock_boundary
      return 0 if curve is None else len(curve.shock_points_m)
    ####

    references = tuple(case.result.reference for case in cases)
    object.__setattr__(
      self,
      'global_shock_sample_counts',
      tuple(closure_curve_count(case) for case in cases),
    )
    object.__setattr__(
      self,
      'reference_axial_station_counts',
      tuple(0 if reference is None else reference.axial_station_count for reference in references),
    )
    object.__setattr__(
      self,
      'reference_transverse_station_counts',
      tuple(0 if reference is None else reference.transverse_station_count for reference in references),
    )
    object.__setattr__(
      self,
      'node_counts',
      tuple(reference.node_count if reference is not None else 0 for reference in references),
    )
    object.__setattr__(
      self,
      'cell_counts',
      tuple(reference.cell_count if reference is not None else 0 for reference in references),
    )
    object.__setattr__(
      self,
      'outlet_heights_m',
      tuple(None if reference is None else reference.outlet_height_m for reference in references),
    )
    object.__setattr__(
      self,
      'maximum_conservative_euler_residuals',
      tuple(
        measurement.maximum_conservative_euler_residual
        for measurement in measurements
      ),
    )

    for name in (
      'outlet_heights_m',
      'maximum_conservative_euler_residuals',
      'outlet_height_delta_residuals_m',
      'free_boundary_shape_delta_residuals_m',
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
        raise ValueError(
          f'{name} must contain finite nonnegative values when supplied'
        )
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'closure_fingerprints',
      'source_band_fingerprints',
    ):
      values = tuple(str(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      object.__setattr__(self, name, values)
    ####
    ambient_fractions = tuple(
      None if value is None else float(value)
      for value in self.ambient_pressure_fractions
    )
    if len(ambient_fractions) != len(cases):
      raise ValueError('ambient_pressure_fractions must match the case count')
    ####
    if any(
      value is not None and (not isfinite(value) or value <= 0.0)
      for value in ambient_fractions
    ):
      raise ValueError(
        'ambient_pressure_fractions must contain finite positive values'
      )
    ####
    object.__setattr__(self, 'ambient_pressure_fractions', ambient_fractions)

    for name in (
      'global_shock_sample_counts',
      'reference_axial_station_counts',
      'reference_transverse_station_counts',
      'node_counts',
      'cell_counts',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative case counts')
      ####
      object.__setattr__(self, name, values)
    ####
    fractions = tuple(float(value) for value in self.geometry_sample_fractions)
    if any(not isfinite(value) or value < 0.0 or value > 1.0 for value in fractions):
      raise ValueError(
        'geometry_sample_fractions must contain finite values in [0, 1]'
      )
    ####
    object.__setattr__(self, 'geometry_sample_fractions', fractions)
    for name in (
      'resolution_order_verified',
      'source_band_consistent',
      'closure_fingerprints_verified',
      'request_parameters_consistent',
      'case_measurements_verified',
      'conservative_euler_evidence_verified',
      'mesh_resolution_verified',
      'geometry_sensitivity_verified',
      'outlet_height_stability_verified',
      'refinement_convergence_verified',
      'upstream_global_physical_closure_verified',
      'physical_closure_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'fidelity_isolation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('geometry_tolerance_m', 'outlet_height_tolerance_m'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainMixedRegimeBoundaryRefinementStatus.CONVERGED
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.resolution_order_verified
      and self.source_band_consistent
      and self.closure_fingerprints_verified
      and self.request_parameters_consistent
      and self.case_measurements_verified
      and self.conservative_euler_evidence_verified
      and self.mesh_resolution_verified
      and self.geometry_sensitivity_verified
      and self.outlet_height_stability_verified
      and self.refinement_convergence_verified
      and self.upstream_global_physical_closure_verified
      and not self.physical_closure_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and not self.external_validation_verified
      and self.fidelity_isolation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': list(self.resolutions),
      'closure_fingerprints': list(self.closure_fingerprints),
      'source_band_fingerprints': list(self.source_band_fingerprints),
      'ambient_pressure_fractions': list(self.ambient_pressure_fractions),
      'counts': {
        'global_shock_sample_counts': list(self.global_shock_sample_counts),
        'reference_axial_station_counts': list(self.reference_axial_station_counts),
        'reference_transverse_station_counts': list(self.reference_transverse_station_counts),
        'node_counts': list(self.node_counts),
        'cell_counts': list(self.cell_counts),
      },
      'outlet_heights_m': list(self.outlet_heights_m),
      'maximum_conservative_euler_residuals': list(
        self.maximum_conservative_euler_residuals
      ),
      'cases': [
        {
          'resolution': case.resolution,
          'solver_status': case.result.status.value,
          'measurement_status': measurement.status.value,
          'reference_verified': measurement.reference_verified,
        }
        for case, measurement in zip(self.cases, self.measurements, strict=True)
      ],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'source_band_consistent': self.source_band_consistent,
        'closure_fingerprints_verified': self.closure_fingerprints_verified,
        'request_parameters_consistent': self.request_parameters_consistent,
        'case_measurements_verified': self.case_measurements_verified,
        'conservative_euler_evidence_verified': (
          self.conservative_euler_evidence_verified
        ),
        'mesh_resolution_verified': self.mesh_resolution_verified,
        'geometry_sensitivity_verified': self.geometry_sensitivity_verified,
        'outlet_height_stability_verified': self.outlet_height_stability_verified,
        'refinement_convergence_verified': self.refinement_convergence_verified,
        'upstream_global_physical_closure_verified': (
          self.upstream_global_physical_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'geometry_sample_fractions': list(self.geometry_sample_fractions),
      'residuals': {
        'outlet_height_delta_residuals_m': list(
          self.outlet_height_delta_residuals_m
        ),
        'free_boundary_shape_delta_residuals_m': list(
          self.free_boundary_shape_delta_residuals_m
        ),
      },
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####
