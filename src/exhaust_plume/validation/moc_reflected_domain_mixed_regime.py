"""Independent audit for the global reflected mixed-regime boundary bridge.

The solver-side bridge is intentionally a scalar variable-entropy reference.
This module audits its provenance and retained fields as data: it does not run
the reference solver, infer a perimeter, or turn a successful audit into a
canonical reflected-MOC or production-chain claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MIXED_REGIME_BOUNDARY_MODEL,
  MocReflectedDomainMixedRegimeBoundaryRequest,
  MocReflectedDomainMixedRegimeBoundaryResult,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeVariableEntropyFreeBoundaryMeasurement,
  measure_mixed_regime_variable_entropy_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_OPERATOR_ID',
  'MocReflectedDomainMixedRegimeBoundaryMeasurementStatus',
  'MocReflectedDomainMixedRegimeBoundaryMeasurement',
  'measure_reflected_domain_mixed_regime_boundary',
)


MOC_REFLECTED_DOMAIN_MIXED_REGIME_BOUNDARY_OPERATOR_ID = (
  'op.moc.reflected-domain-mixed-regime-boundary'
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
  residual_channel_coverage: dict[str, bool] = MappingProxyType({})
  residual_channel_validity: dict[str, bool] = MappingProxyType({})
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
        None if self.candidate is None else self.candidate.request.as_report()
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
