"""Solver-owned extension of a bounded global boundary pressure frame.

The frame-negotiation operator reports the stations that a fresh exact-Euler
ambient march attempted beyond its retained pressure target.  This module
implements the next, deliberately narrow physics seam: when the requested
extension is outside the downstream response overlay and the retained terminal
pressure is independently the source ambient pressure, the solver may extend
the *ambient pressure law* to the requested stations.  The global solver still
owns every boundary ordinate, tangent, and state.

This is not endpoint holding or profile extrapolation.  It is a new target
segment generated from the declared uniform ambient boundary condition and
then consumed by a fresh solver invocation.  The result remains research-only
until the outer joint closure, refinement, and external validation gates pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_global_boundary_frame_negotiation import (
  MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_EXTENSION_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryFrameExtensionStatus',
  'MocReflectedDomainGlobalBoundaryFrameExtensionRequest',
  'MocReflectedDomainGlobalBoundaryFrameExtensionResult',
  'build_reflected_domain_global_boundary_frame_extension_request',
  'extend_reflected_domain_global_boundary_frame',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_EXTENSION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-frame-extension'
)
_AMBIENT_BOUNDARY_LAW = (
  'solver-owned-uniform-ambient-static-pressure-extension-v1'
)


def _is_digest(value: object) -> bool:
  text = str(value)
  return bool(
    len(text) == 64
    and all(character in '0123456789abcdef' for character in text)
  )
####


class MocReflectedDomainGlobalBoundaryFrameExtensionStatus(str, Enum):
  """Outcome of one solver-owned pressure-frame extension attempt."""

  EXTENSION_GENERATED = 'solver-owned-ambient-frame-extension-generated'
  NO_EXTENSION_REQUIRED = 'solver-owned-frame-extension-not-required'
  LINEAGE_FAILURE = 'global-boundary-frame-extension-lineage-failure'
  AMBIENT_LAW_FAILURE = 'global-boundary-frame-extension-ambient-law-failure'
  EXTENSION_BUDGET_FAILURE = 'global-boundary-frame-extension-budget-failure'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryFrameExtensionRequest:
  """Exact request for extending a target with the solver's ambient law."""

  source_closure_fingerprint: str
  source_proposal_fingerprint: str
  frame_negotiation: MocReflectedDomainGlobalBoundaryFrameNegotiationResult
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget
  ambient_pressure_Pa: float
  consumer_id: str
  position_tolerance_m: float = 1.0e-9
  pressure_tolerance_fraction: float = 1.0e-9

  def __post_init__(self) -> None:
    for name in (
      'source_closure_fingerprint',
      'source_proposal_fingerprint',
    ):
      if not _is_digest(getattr(self, name)):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
      ####
    ####
    if not isinstance(
      self.frame_negotiation,
      MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
    ):
      raise TypeError(
        'frame_negotiation must be a typed boundary-frame negotiation result'
      )
    ####
    if not isinstance(
      self.base_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'base_target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
      )
    ####
    if (
      self.frame_negotiation.source_closure_fingerprint
      != self.source_closure_fingerprint
      or self.frame_negotiation.source_proposal_fingerprint
      != self.source_proposal_fingerprint
    ):
      raise ValueError(
        'frame negotiation fingerprints must match the extension request'
      )
    ####
    if (
      self.base_target.source_closure_fingerprint
      != self.source_closure_fingerprint
      or self.base_target.source_proposal_fingerprint
      != self.source_proposal_fingerprint
    ):
      raise ValueError(
        'base target does not retain the exact source/proposal lineage'
      )
    ####
    if self.base_target.composition_mode != 'direct':
      raise ValueError(
        'frame extension requires the direct solver-owned base target; '
        'nested pressure overlays are not accepted'
      )
    ####
    ambient_pressure = float(self.ambient_pressure_Pa)
    if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
      raise ValueError('ambient_pressure_Pa must be finite and positive')
    ####
    tolerance = float(self.position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    pressure_tolerance = float(self.pressure_tolerance_fraction)
    if not isfinite(pressure_tolerance) or pressure_tolerance < 0.0:
      raise ValueError(
        'pressure_tolerance_fraction must be finite and nonnegative'
      )
    ####
    consumer_id = str(self.consumer_id)
    if not consumer_id:
      raise ValueError('consumer_id must be non-empty')
    ####
    available_min, available_max = (
      self.frame_negotiation.request.available_x_interval_m
    )
    base_min, base_max = (
      self.base_target.x_stations_m[0],
      self.base_target.x_stations_m[-1],
    )
    if (
      abs(available_min - base_min) > tolerance
      or abs(available_max - base_max) > tolerance
    ):
      raise ValueError(
        'base target must cover exactly the negotiated available frame'
      )
    ####
    object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    object.__setattr__(self, 'position_tolerance_m', tolerance)
    object.__setattr__(self, 'pressure_tolerance_fraction', pressure_tolerance)
    object.__setattr__(self, 'consumer_id', consumer_id)
  ####

  @property
  def requested_x_stations_m(self) -> tuple[float, ...]:
    return self.frame_negotiation.request.requested_x_stations_m
  ####

  @property
  def available_x_interval_m(self) -> tuple[float, float]:
    return self.frame_negotiation.request.available_x_interval_m
  ####

  @property
  def requested_x_interval_m(self) -> tuple[float, float]:
    return self.frame_negotiation.request.requested_x_interval_m
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'frame_negotiation': self.frame_negotiation.as_report(),
      'base_target': self.base_target.as_report(),
      'available_x_interval_m': self.available_x_interval_m,
      'requested_x_interval_m': self.requested_x_interval_m,
      'requested_x_stations_m': self.requested_x_stations_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'ambient_boundary_law': _AMBIENT_BOUNDARY_LAW,
      'consumer_id': self.consumer_id,
      'position_tolerance_m': self.position_tolerance_m,
      'pressure_tolerance_fraction': self.pressure_tolerance_fraction,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryFrameExtensionResult:
  """Audited target extension; not a canonical mixed-regime closure."""

  status: MocReflectedDomainGlobalBoundaryFrameExtensionStatus
  request: MocReflectedDomainGlobalBoundaryFrameExtensionRequest
  extended_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  extension_x_stations_m: tuple[float, ...] = ()
  generated_pressure_Pa: tuple[float, ...] = ()
  terminal_pressure_ambient_relative_residual: float | None = None
  lineage_verified: bool = False
  ambient_boundary_law_verified: bool = False
  station_extension_verified: bool = False
  solver_owned_pressure_verified: bool = False
  extrapolation_blocked: bool = True
  endpoint_hold_blocked: bool = True
  geometry_injection_blocked: bool = True
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  configuration: dict[str, Any] | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus,
    ):
      raise TypeError('status must be a typed frame-extension status')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
    ):
      raise TypeError('request must be a typed frame-extension request')
    ####
    if self.extended_target is not None and not isinstance(
      self.extended_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'extended_target must be a MocPhysicalFieldEulerBoundaryPressureTarget '
        'or None'
      )
    ####
    for name in (
      'lineage_verified',
      'ambient_boundary_law_verified',
      'station_extension_verified',
      'solver_owned_pressure_verified',
      'extrapolation_blocked',
      'endpoint_hold_blocked',
      'geometry_injection_blocked',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified or self.production_claim_allowed:
      raise ValueError('frame extension cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('frame extension must block chain promotion')
    ####
    extension_stations = tuple(float(value) for value in self.extension_x_stations_m)
    generated_pressures = tuple(float(value) for value in self.generated_pressure_Pa)
    if len(extension_stations) != len(generated_pressures):
      raise ValueError(
        'extension_x_stations_m and generated_pressure_Pa must have equal lengths'
      )
    ####
    if any(not isfinite(value) for value in extension_stations):
      raise ValueError('extension_x_stations_m must contain finite values')
    ####
    if any(
      second <= first
      for first, second in zip(extension_stations, extension_stations[1:])
    ):
      raise ValueError('extension_x_stations_m must be strictly increasing')
    ####
    if any(
      not isfinite(value) or value <= 0.0 for value in generated_pressures
    ):
      raise ValueError('generated_pressure_Pa must contain finite positive values')
    ####
    if self.terminal_pressure_ambient_relative_residual is not None:
      residual = float(self.terminal_pressure_ambient_relative_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'terminal_pressure_ambient_relative_residual must be finite and '
          'nonnegative'
        )
      ####
      object.__setattr__(
        self,
        'terminal_pressure_ambient_relative_residual',
        residual,
      )
    ####
    object.__setattr__(self, 'extension_x_stations_m', extension_stations)
    object.__setattr__(self, 'generated_pressure_Pa', generated_pressures)
    object.__setattr__(self, 'configuration', dict(self.configuration or {}))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def extension_generated(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryFrameExtensionStatus
      .EXTENSION_GENERATED
      and self.lineage_verified
      and self.ambient_boundary_law_verified
      and self.station_extension_verified
      and self.solver_owned_pressure_verified
      and self.extended_target is not None
    )
  ####

  @property
  def converged(self) -> bool:
    """Whether the extension request itself passed, not the fresh solve."""

    return bool(
      self.extension_generated
      or (
        self.status
        is MocReflectedDomainGlobalBoundaryFrameExtensionStatus
        .NO_EXTENSION_REQUIRED
        and self.lineage_verified
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_EXTENSION_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'extension_generated': self.extension_generated,
      'source_closure_fingerprint': self.request.source_closure_fingerprint,
      'source_proposal_fingerprint': self.request.source_proposal_fingerprint,
      'available_x_interval_m': self.request.available_x_interval_m,
      'requested_x_interval_m': self.request.requested_x_interval_m,
      'extension_x_stations_m': self.extension_x_stations_m,
      'generated_pressure_Pa': self.generated_pressure_Pa,
      'terminal_pressure_ambient_relative_residual': (
        self.terminal_pressure_ambient_relative_residual
      ),
      'lineage_verified': self.lineage_verified,
      'ambient_boundary_law_verified': self.ambient_boundary_law_verified,
      'station_extension_verified': self.station_extension_verified,
      'solver_owned_pressure_verified': self.solver_owned_pressure_verified,
      'extrapolation_blocked': self.extrapolation_blocked,
      'endpoint_hold_blocked': self.endpoint_hold_blocked,
      'geometry_injection_blocked': self.geometry_injection_blocked,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'extended_target': (
        None if self.extended_target is None else self.extended_target.as_report()
      ),
      'request': self.request.as_report(),
      'configuration': self.configuration,
      'claim_status': (
        'research-only-solver-owned-ambient-frame-extension; a fresh exact '
        'solver must consume and audit the new stations before any closure '
        'or promotion claim'
      ),
      'message': self.message,
    }
  ####
####


def build_reflected_domain_global_boundary_frame_extension_request(
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  frame_negotiation: MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget,
  *,
  consumer_id: str = 'moc-global-boundary-frame-extension-v1',
  position_tolerance_m: float = 1.0e-9,
  pressure_tolerance_fraction: float = 1.0e-9,
) -> MocReflectedDomainGlobalBoundaryFrameExtensionRequest:
  """Bind an ambient-law extension to one closure, proposal, and frame."""

  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not isinstance(
    frontier_request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'frontier_request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    frame_negotiation,
    MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  ):
    raise TypeError(
      'frame_negotiation must be a '
      'MocReflectedDomainGlobalBoundaryFrameNegotiationResult'
    )
  ####
  if not isinstance(
    base_target,
    MocPhysicalFieldEulerBoundaryPressureTarget,
  ):
    raise TypeError(
      'base_target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
    )
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  proposal_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
    frontier_request.proposal
  )
  if (
    frame_negotiation.source_closure_fingerprint != source_fingerprint
    or frame_negotiation.source_proposal_fingerprint != proposal_fingerprint
    or frontier_request.source_closure_fingerprint != source_fingerprint
    or not frontier_request.lineage_verified
  ):
    raise ValueError(
      'frame negotiation does not retain the exact closure/proposal lineage'
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    raise ValueError(
      'frame extension requires a locally physically verified source closure'
    )
  ####
  source_band = source_closure.source_band
  ambient_pressure = None if source_band is None else source_band.ambient_pressure_Pa
  if ambient_pressure is None:
    raise ValueError('source closure retained no solver-owned ambient pressure')
  ####
  return MocReflectedDomainGlobalBoundaryFrameExtensionRequest(
    source_closure_fingerprint=source_fingerprint,
    source_proposal_fingerprint=proposal_fingerprint,
    frame_negotiation=frame_negotiation,
    base_target=base_target,
    ambient_pressure_Pa=float(ambient_pressure),
    consumer_id=consumer_id,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance_fraction=pressure_tolerance_fraction,
  )
####


def _configuration(
  request: MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
) -> dict[str, Any]:
  return {
    'consumer_id': request.consumer_id,
    'ambient_boundary_law': _AMBIENT_BOUNDARY_LAW,
    'position_tolerance_m': request.position_tolerance_m,
    'pressure_tolerance_fraction': request.pressure_tolerance_fraction,
    'geometry_policy': 'solver-owned-boundary-no-target-geometry-injection-v1',
    'profile_policy': 'ambient-law-extension-only-no-extrapolation-no-endpoint-hold-v1',
  }
####


def _failure(
  request: MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
  status: MocReflectedDomainGlobalBoundaryFrameExtensionStatus,
  message: str,
  *,
  lineage_verified: bool = False,
  ambient_boundary_law_verified: bool = False,
  terminal_residual: float | None = None,
) -> MocReflectedDomainGlobalBoundaryFrameExtensionResult:
  return MocReflectedDomainGlobalBoundaryFrameExtensionResult(
    status=status,
    request=request,
    terminal_pressure_ambient_relative_residual=terminal_residual,
    lineage_verified=lineage_verified,
    ambient_boundary_law_verified=ambient_boundary_law_verified,
    configuration=_configuration(request),
    message=message,
  )
####


def extend_reflected_domain_global_boundary_frame(
  request: MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
) -> MocReflectedDomainGlobalBoundaryFrameExtensionResult:
  """Generate only a bounded uniform-ambient extension of the target frame."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalBoundaryFrameExtensionRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalBoundaryFrameExtensionRequest'
    )
  ####
  negotiation = request.frame_negotiation
  lineage_verified = bool(
    negotiation.lineage_verified
    and negotiation.frame_request_verified
    and negotiation.source_closure_fingerprint
    == request.source_closure_fingerprint
    and negotiation.source_proposal_fingerprint
    == request.source_proposal_fingerprint
  )
  if not lineage_verified:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.LINEAGE_FAILURE,
      'frame negotiation does not carry verified closure/proposal lineage',
    )
  ####
  if negotiation.status is not (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
    .FRAME_EXTENSION_REQUIRED
  ):
    if negotiation.status is (
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .COVERED_SOLVER_FRAME
    ):
      return MocReflectedDomainGlobalBoundaryFrameExtensionResult(
        status=(
          MocReflectedDomainGlobalBoundaryFrameExtensionStatus
          .NO_EXTENSION_REQUIRED
        ),
        request=request,
        extended_target=request.base_target,
        lineage_verified=True,
        station_extension_verified=True,
        solver_owned_pressure_verified=True,
        configuration=_configuration(request),
        message='negotiated solver-owned frame already covers the requested stations',
      )
    ####
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.EXTENSION_BUDGET_FAILURE,
      'the frame negotiation is not eligible for a bounded extension',
      lineage_verified=True,
    )
  ####
  if not negotiation.extension_budget_verified:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.EXTENSION_BUDGET_FAILURE,
      'requested frame extension exceeds the configured solver-owned budget',
      lineage_verified=True,
    )
  ####
  tolerance = request.position_tolerance_m
  base_target = request.base_target
  available_min, available_max = request.available_x_interval_m
  base_min, base_max = base_target.x_stations_m[0], base_target.x_stations_m[-1]
  if (
    abs(available_min - base_min) > tolerance
    or abs(available_max - base_max) > tolerance
  ):
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.LINEAGE_FAILURE,
      'base target frame changed after negotiation',
      lineage_verified=True,
    )
  ####
  requested_min, requested_max = request.requested_x_interval_m
  if requested_min < available_min - tolerance:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'the ambient extension law cannot fill a lower-frame request',
      lineage_verified=True,
    )
  ####
  terminal_pressure = float(base_target.static_pressure_Pa[-1])
  terminal_residual = abs(terminal_pressure - request.ambient_pressure_Pa) / max(
    abs(request.ambient_pressure_Pa),
    1.0,
  )
  if terminal_residual > request.pressure_tolerance_fraction:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'the retained terminal target pressure is not the declared source '
      'ambient pressure; no endpoint hold or profile extrapolation was attempted',
      lineage_verified=True,
      terminal_residual=terminal_residual,
    )
  ####
  extension_stations = tuple(
    station
    for station in request.requested_x_stations_m
    if station > base_max + tolerance
  )
  if requested_max <= base_max + tolerance or not extension_stations:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'frame negotiation requested no strictly new upper solver station',
      lineage_verified=True,
      ambient_boundary_law_verified=True,
      terminal_residual=terminal_residual,
    )
  ####
  stations = tuple((*base_target.x_stations_m, *extension_stations))
  if any(second <= first for first, second in zip(stations, stations[1:])):
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'ambient-law extension stations are not strictly downstream ordered',
      lineage_verified=True,
      ambient_boundary_law_verified=True,
      terminal_residual=terminal_residual,
    )
  ####
  pressures = tuple(
    request.ambient_pressure_Pa if station > base_max + tolerance else float(
      base_target.pressure_at_x(
        station,
        position_tolerance_m=tolerance,
      )
    )
    for station in stations
  )
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'ambient-law extension generated a nonphysical pressure',
      lineage_verified=True,
      ambient_boundary_law_verified=True,
      terminal_residual=terminal_residual,
    )
  ####
  extended_target = MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=stations,
    static_pressure_Pa=pressures,
    source_id=(
      f'{request.consumer_id}:ambient-law:{request.source_closure_fingerprint}'
    ),
    # Boundary ordinates and tangents are intentionally omitted.  The fresh
    # global solver owns them; carrying the old geometry here would violate
    # the extension contract.
    boundary_points_m=(),
    tangent_rad=(),
    source_closure_fingerprint=request.source_closure_fingerprint,
    source_proposal_fingerprint=request.source_proposal_fingerprint,
  )
  station_extension_verified = bool(
    extended_target.x_stations_m[-1] >= requested_max - tolerance
    and tuple(extended_target.x_stations_m[:len(base_target.x_stations_m)])
    == base_target.x_stations_m
    and all(
      abs(value - request.ambient_pressure_Pa)
      <= request.pressure_tolerance_fraction
      * max(abs(request.ambient_pressure_Pa), 1.0)
      for value in extended_target.static_pressure_Pa[len(base_target.x_stations_m):]
    )
  )
  if not station_extension_verified:
    return _failure(
      request,
      MocReflectedDomainGlobalBoundaryFrameExtensionStatus.AMBIENT_LAW_FAILURE,
      'generated target did not retain the exact solver-requested ambient stations',
      lineage_verified=True,
      ambient_boundary_law_verified=True,
      terminal_residual=terminal_residual,
    )
  ####
  return MocReflectedDomainGlobalBoundaryFrameExtensionResult(
    status=MocReflectedDomainGlobalBoundaryFrameExtensionStatus.EXTENSION_GENERATED,
    request=request,
    extended_target=extended_target,
    extension_x_stations_m=extension_stations,
    generated_pressure_Pa=tuple(
      request.ambient_pressure_Pa for _ in extension_stations
    ),
    terminal_pressure_ambient_relative_residual=terminal_residual,
    lineage_verified=True,
    ambient_boundary_law_verified=True,
    station_extension_verified=station_extension_verified,
    solver_owned_pressure_verified=True,
    configuration=_configuration(request),
    message=(
      'solver-owned uniform ambient pressure law extended the target frame; '
      'a fresh exact global solve must generate the boundary geometry and '
      're-audit all residual channels'
    ),
  )
####
