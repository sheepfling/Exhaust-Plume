"""Typed post-shock interface handoff after bounded MOC placement.

The bounded placement seam proves one local intersection between a transported
characteristic and a resolved neighboring frontier.  This module carries the
audited scalar shock state across that interface as explicit upstream and
downstream boundary samples.  It is the input contract for the next coupled
mixed-regime field iteration; it does not solve that field, move a free
boundary, or promote a shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, log, pi
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import solve_normal_shock_terminal
from exhaust_plume.models.moc.physical_cell import MocPhysicalPostShockFieldResult
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.transonic_placement import (
  MocTransonicPlacementResult,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryResult,
)

__all__ = (
  'MocTransonicShockInterfaceStatus',
  'MocTransonicShockInterfaceSample',
  'MocTransonicShockInterfaceProfile',
  'MocTransonicShockInterfaceProfileBuildStatus',
  'MocTransonicShockInterfaceProfileRequest',
  'MocTransonicShockInterfaceProfileBuildResult',
  'MocTransonicShockInterfaceFieldProfileStatus',
  'MocTransonicShockInterfaceFieldProfileRequest',
  'MocTransonicShockInterfaceFieldProfileResult',
  'MocTransonicShockInterfaceRequest',
  'MocTransonicShockInterfaceResult',
  'build_moc_transonic_shock_interface_profile',
  'build_moc_transonic_shock_interface_profile_from_field',
  'solve_moc_transonic_shock_interface',
)


TRANSONIC_INTERFACE_MODEL = 'research-solver-owned-transonic-shock-interface-v1'


class MocTransonicShockInterfaceStatus(str, Enum):
  """Outcome of one solver-owned local shock-interface handoff."""

  CONVERGED_BOUNDED_INTERFACE = (
    'converged-bounded-transonic-shock-interface'
  )
  INVALID_INPUT = 'invalid_input'
  PLACEMENT_REQUIRED = 'transonic-interface-placement-required'
  GEOMETRY_FAILURE = 'transonic-interface-geometry-failure'
  UPSTREAM_LINEAGE_FAILURE = 'transonic-interface-upstream-lineage-failure'
  DOWNSTREAM_STATE_FAILURE = 'transonic-interface-downstream-state-failure'
  INDEPENDENT_AUDIT_FAILURE = 'transonic-interface-independent-audit-failure'
####


def _finite(name: str, value: object) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric):
    raise ValueError(f'{name} must be finite')
  ####
  return numeric
####


def _state_residual(
  actual: CharacteristicState,
  expected: CharacteristicState,
) -> float:
  return max(
    abs(actual.x_m - expected.x_m),
    abs(actual.y_m - expected.y_m),
    abs(actual.theta_rad - expected.theta_rad),
    abs(actual.mach - expected.mach),
    abs(actual.gamma - expected.gamma),
  )
####


def _pressure_residual(actual: float, expected: float) -> float:
  if actual <= 0.0 or expected <= 0.0:
    return float('inf')
  ####
  return abs(log(actual / expected))
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceSample:
  """One scalar state on either side of the local shock interface.

  Unlike ``CharacteristicState``, this type permits the downstream subsonic
  Mach number.  It is intentionally not accepted by the supersonic MOC
  compatibility network.
  """

  point_m: tuple[float, float]
  mach: float
  flow_angle_rad: float
  static_pressure_Pa: float
  total_pressure_Pa: float
  gamma: float

  def __post_init__(self) -> None:
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('interface sample point must contain two coordinates') from None
    ####
    if not all(isfinite(value) for value in point):
      raise ValueError('interface sample point must contain finite coordinates')
    ####
    for name, value in (
      ('mach', self.mach),
      ('static_pressure_Pa', self.static_pressure_Pa),
      ('total_pressure_Pa', self.total_pressure_Pa),
      ('gamma', self.gamma),
    ):
      numeric = _finite(name, value)
      if numeric <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    flow_angle = _finite('flow_angle_rad', self.flow_angle_rad)
    object.__setattr__(self, 'flow_angle_rad', flow_angle)
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    object.__setattr__(self, 'point_m', point)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'point_m': list(self.point_m),
      'mach': self.mach,
      'flow_angle_rad': self.flow_angle_rad,
      'static_pressure_Pa': self.static_pressure_Pa,
      'total_pressure_Pa': self.total_pressure_Pa,
      'gamma': self.gamma,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceProfile:
  """A sampled downstream profile on a cross-section shock handoff.

  The scalar interface result identifies one local placement point.  A
  coupled finite-volume field needs a state on every inlet face instead.  This
  contract carries that profile without extrapolation: samples must lie on one
  vertical cross-section, cover a strictly ordered ordinate interval, and
  retain both supersonic upstream and subsonic downstream regime evidence.
  The coupled field accepts this profile at the original field inlet, or
  through its distinct interior-profile research mode, which starts a new
  downstream field exactly at the retained cross-section.  The latter still
  does not close the surrounding upstream/downstream mixed-regime field or
  authorize production promotion.
  """

  upstream_samples: tuple[MocTransonicShockInterfaceSample, ...]
  downstream_samples: tuple[MocTransonicShockInterfaceSample, ...]
  interface_normal_angle_rad: float = 0.0
  profile_id: str = 'solver-owned-transonic-shock-interface-profile-v1'
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    upstream_samples = tuple(self.upstream_samples)
    downstream_samples = tuple(self.downstream_samples)
    if len(upstream_samples) < 2:
      raise ValueError('shock-interface profile requires at least two samples')
    ####
    if any(
      not isinstance(sample, MocTransonicShockInterfaceSample)
      for sample in (*upstream_samples, *downstream_samples)
    ):
      raise TypeError(
        'shock-interface profile samples must contain '
        'MocTransonicShockInterfaceSample values'
      )
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
    normal_angle = _finite(
      'interface_normal_angle_rad',
      self.interface_normal_angle_rad,
    )
    object.__setattr__(self, 'interface_normal_angle_rad', normal_angle)
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'profile_id', profile_id)
    if len(downstream_samples) != len(upstream_samples):
      raise ValueError(
        'upstream and downstream shock-interface profiles must have equal lengths'
      )
    ####
    x_reference = upstream_samples[0].point_m[0]
    x_tolerance = self.position_tolerance_m
    if any(
      abs(sample.point_m[0] - x_reference) > x_tolerance
      for sample in (*upstream_samples[1:], *downstream_samples)
    ):
      raise ValueError(
        'shock-interface profile samples must lie on one cross-section x'
      )
    ####
    upstream_ordinates = tuple(sample.point_m[1] for sample in upstream_samples)
    downstream_ordinates = tuple(sample.point_m[1] for sample in downstream_samples)
    if any(
      abs(first - second) > self.position_tolerance_m
      for first, second in zip(upstream_ordinates, downstream_ordinates)
    ):
      raise ValueError(
        'upstream and downstream shock-interface profile ordinates must match'
      )
    ####
    ordinates = upstream_ordinates
    if any(
      second <= first + self.position_tolerance_m
      for first, second in zip(ordinates, ordinates[1:])
    ):
      raise ValueError(
        'shock-interface profile ordinates must be strictly increasing'
      )
    ####
    gammas = tuple(
      sample.gamma for sample in (*upstream_samples, *downstream_samples)
    )
    if max(gammas) - min(gammas) > self.state_tolerance:
      raise ValueError('shock-interface profile samples must use one gamma')
    ####
    if any(sample.mach <= 1.0 for sample in upstream_samples):
      raise ValueError(
        'shock-interface profile upstream samples must be supersonic'
      )
    ####
    if any(sample.mach >= 1.0 for sample in downstream_samples):
      raise ValueError(
        'shock-interface profile downstream samples must be subsonic'
      )
    ####
    object.__setattr__(self, 'upstream_samples', upstream_samples)
    object.__setattr__(self, 'downstream_samples', downstream_samples)
  ####

  @property
  def cross_section_x_m(self) -> float:
    """Return the retained cross-section ordinate."""

    return self.upstream_samples[0].point_m[0]
  ####

  @property
  def lower_ordinate_m(self) -> float:
    return self.upstream_samples[0].point_m[1]
  ####

  @property
  def upper_ordinate_m(self) -> float:
    return self.upstream_samples[-1].point_m[1]
  ####

  @property
  def gamma(self) -> float:
    return self.upstream_samples[0].gamma
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'profile_id': self.profile_id,
      'interface_normal_angle_rad': self.interface_normal_angle_rad,
      'cross_section_x_m': self.cross_section_x_m,
      'lower_ordinate_m': self.lower_ordinate_m,
      'upper_ordinate_m': self.upper_ordinate_m,
      'sample_count': len(self.upstream_samples),
      'upstream_samples': [
        sample.as_report() for sample in self.upstream_samples
      ],
      'downstream_samples': [
        sample.as_report() for sample in self.downstream_samples
      ],
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'claim_status': (
        'research-only-cross-section-shock-interface-profile; interior '
        'placement and surrounding mixed-regime closure remain open'
      ),
    }
  ####
####


class MocTransonicShockInterfaceProfileBuildStatus(str, Enum):
  """Outcome of deriving a normal-shock profile from upstream samples."""

  CONVERGED_NORMAL_SHOCK_PROFILE = (
    'converged-normal-shock-interface-profile'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_PROFILE_FAILURE = 'transonic-interface-upstream-profile-failure'
  NORMAL_ALIGNMENT_FAILURE = 'transonic-interface-normal-alignment-failure'
  SHOCK_STATE_FAILURE = 'transonic-interface-normal-shock-state-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'transonic-interface-profile-independent-audit-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceProfileRequest:
  """Inputs for a solver-owned normal-shock cross-section profile.

  The caller must provide a spatially ordered, supersonic upstream profile.
  Each sample is required to be aligned with the retained interface normal,
  so this builder only derives a local normal-shock jump.  It does not infer
  an interior shock surface or a global mixed-regime closure.
  """

  upstream_samples: tuple[MocTransonicShockInterfaceSample, ...]
  interface_normal_angle_rad: float = 0.0
  profile_id: str = 'solver-owned-normal-shock-interface-profile-v1'
  normal_alignment_tolerance_rad: float = 1.0e-8
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    samples = tuple(self.upstream_samples)
    if any(
      not isinstance(sample, MocTransonicShockInterfaceSample)
      for sample in samples
    ):
      raise TypeError(
        'upstream_samples must contain MocTransonicShockInterfaceSample values'
      )
    ####
    object.__setattr__(self, 'upstream_samples', samples)
    normal_angle = _finite(
      'interface_normal_angle_rad',
      self.interface_normal_angle_rad,
    )
    object.__setattr__(self, 'interface_normal_angle_rad', normal_angle)
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'profile_id', profile_id)
    for name in (
      'normal_alignment_tolerance_rad',
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': 'research-normal-shock-interface-profile-builder-v1',
      'profile_id': self.profile_id,
      'interface_normal_angle_rad': self.interface_normal_angle_rad,
      'sample_count': len(self.upstream_samples),
      'upstream_samples': [
        sample.as_report() for sample in self.upstream_samples
      ],
      'normal_alignment_tolerance_rad': self.normal_alignment_tolerance_rad,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceProfileBuildResult:
  """Audited normal-shock profile derived from caller-owned upstream data."""

  status: MocTransonicShockInterfaceProfileBuildStatus
  request: MocTransonicShockInterfaceProfileRequest
  profile: MocTransonicShockInterfaceProfile | None = None
  independent_measurement: Any | None = None
  upstream_profile_verified: bool = False
  normal_alignment_verified: bool = False
  downstream_state_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicShockInterfaceProfileBuildStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceProfileBuildStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocTransonicShockInterfaceProfileRequest,
    ):
      raise TypeError(
        'request must be a MocTransonicShockInterfaceProfileRequest'
      )
    ####
    if self.profile is not None and not isinstance(
      self.profile,
      MocTransonicShockInterfaceProfile,
    ):
      raise TypeError(
        'profile must be a MocTransonicShockInterfaceProfile or None'
      )
    ####
    for name in (
      'upstream_profile_verified',
      'normal_alignment_verified',
      'downstream_state_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    audit = self.independent_measurement
    return bool(
      self.status is (
        MocTransonicShockInterfaceProfileBuildStatus
        .CONVERGED_NORMAL_SHOCK_PROFILE
      )
      and self.profile is not None
      and self.upstream_profile_verified
      and self.normal_alignment_verified
      and self.downstream_state_verified
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A local profile does not close the surrounding mixed-regime field."""

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
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': 'research-normal-shock-interface-profile-builder-v1',
      'converged': self.converged,
      'upstream_profile_verified': self.upstream_profile_verified,
      'normal_alignment_verified': self.normal_alignment_verified,
      'downstream_state_verified': self.downstream_state_verified,
      'profile': None if self.profile is None else self.profile.as_report(),
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-normal-shock-cross-section-profile; interior placement, '
        'surrounding mixed-regime closure, physical shock-cell length, and '
        'external validation remain open'
      ),
      'request': self.request.as_report(),
      'message': self.message,
    }
  ####
####


def _line_angle_residual(actual: float, expected: float) -> float:
  """Return the smallest residual between two undirected normal lines."""

  return abs((actual - expected + 0.5 * pi) % pi - 0.5 * pi)
####


def _sample_static_pressure(sample: MocTransonicShockInterfaceSample) -> float:
  factor = 1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach**2
  return sample.total_pressure_Pa / factor ** (
    sample.gamma / (sample.gamma - 1.0)
  )
####


def _static_pressure_from_state_total_pressure(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (state.gamma - 1.0) * state.mach**2
  return float(total_pressure_Pa) / factor ** (
    state.gamma / (state.gamma - 1.0)
  )
####


def _normal_shock_profile_sample(
  upstream: MocTransonicShockInterfaceSample,
  request: MocTransonicShockInterfaceProfileRequest,
) -> MocTransonicShockInterfaceSample | None:
  """Derive one downstream sample through the exact normal-shock primitive."""

  upstream_state = CharacteristicState(
    x_m=upstream.point_m[0],
    y_m=upstream.point_m[1],
    theta_rad=upstream.flow_angle_rad,
    mach=upstream.mach,
    gamma=upstream.gamma,
  )
  terminal = solve_normal_shock_terminal(
    upstream_state,
    upstream_pressure_Pa=upstream.static_pressure_Pa,
    shock_point_m=upstream.point_m,
  )
  if (
    not terminal.converged
    or terminal.downstream_mach is None
    or terminal.downstream_flow_angle_rad is None
    or terminal.downstream_pressure_Pa is None
    or terminal.downstream_total_pressure_Pa is None
  ):
    return None
  ####
  if _pressure_residual(
    upstream.total_pressure_Pa,
    terminal.upstream_total_pressure_Pa
    if terminal.upstream_total_pressure_Pa is not None
    else 0.0,
  ) > request.pressure_tolerance:
    return None
  ####
  return MocTransonicShockInterfaceSample(
    point_m=upstream.point_m,
    mach=terminal.downstream_mach,
    flow_angle_rad=terminal.downstream_flow_angle_rad,
    static_pressure_Pa=terminal.downstream_pressure_Pa,
    total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    gamma=upstream.gamma,
  )
####


class MocTransonicShockInterfaceFieldProfileStatus(str, Enum):
  """Outcome of sampling a retained physical field into a shock profile."""

  CONVERGED_FIELD_BOUND_PROFILE = (
    'converged-field-bound-transonic-shock-interface-profile'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_SAMPLING_UNAVAILABLE = (
    'transonic-interface-physical-field-sampling-unavailable'
  )
  CROSS_SECTION_FAILURE = 'transonic-interface-field-cross-section-failure'
  FIELD_SAMPLE_FAILURE = 'transonic-interface-field-sample-failure'
  PROFILE_BUILD_FAILURE = 'transonic-interface-field-profile-build-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'transonic-interface-field-profile-independent-audit-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceFieldProfileRequest:
  """Request an exact-state sample from a retained physical post-shock field.

  ``sample_points_m`` are caller-selected points, but every state and total
  pressure is read from the retained field sampler.  The request therefore
  cannot extrapolate a state or fabricate a profile outside the field domain.
  """

  field: MocPhysicalPostShockFieldResult
  sample_points_m: tuple[tuple[float, float], ...]
  interface_normal_angle_rad: float = 0.0
  profile_id: str = 'global-physical-field-bound-normal-shock-profile-v1'
  normal_alignment_tolerance_rad: float = 1.0e-2
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8
  source: str = 'global-physical-field-cross-section-sampler-v1'

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocPhysicalPostShockFieldResult):
      raise TypeError('field must be a MocPhysicalPostShockFieldResult')
    ####
    points = tuple(
      (float(point[0]), float(point[1])) for point in self.sample_points_m
    )
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('sample_points_m must contain finite points')
    ####
    object.__setattr__(self, 'sample_points_m', points)
    normal_angle = _finite(
      'interface_normal_angle_rad',
      self.interface_normal_angle_rad,
    )
    object.__setattr__(self, 'interface_normal_angle_rad', normal_angle)
    profile_id = str(self.profile_id)
    if not profile_id:
      raise ValueError('profile_id must not be empty')
    ####
    object.__setattr__(self, 'profile_id', profile_id)
    source = str(self.source)
    if not source:
      raise ValueError('source must not be empty')
    ####
    object.__setattr__(self, 'source', source)
    for name in (
      'normal_alignment_tolerance_rad',
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': 'research-physical-field-bound-interface-profile-v1',
      'source': self.source,
      'profile_id': self.profile_id,
      'field_status': self.field.status.value,
      'field_physical_closure_verified': self.field.physical_closure_verified,
      'field_state_sampling_available': self.field.state_sampling_available,
      'sample_points_m': [list(point) for point in self.sample_points_m],
      'sample_count': len(self.sample_points_m),
      'interface_normal_angle_rad': self.interface_normal_angle_rad,
      'normal_alignment_tolerance_rad': self.normal_alignment_tolerance_rad,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceFieldProfileResult:
  """Audited normal-shock profile bound to a retained physical field."""

  status: MocTransonicShockInterfaceFieldProfileStatus
  request: MocTransonicShockInterfaceFieldProfileRequest
  field: MocPhysicalPostShockFieldResult | None = None
  upstream_samples: tuple[MocTransonicShockInterfaceSample, ...] = ()
  profile: MocTransonicShockInterfaceProfile | None = None
  profile_build: MocTransonicShockInterfaceProfileBuildResult | None = None
  independent_measurement: Any | None = None
  field_lineage_verified: bool = False
  field_sampling_verified: bool = False
  profile_build_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicShockInterfaceFieldProfileStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicShockInterfaceFieldProfileStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocTransonicShockInterfaceFieldProfileRequest,
    ):
      raise TypeError(
        'request must be a MocTransonicShockInterfaceFieldProfileRequest'
      )
    ####
    if self.field is not None and not isinstance(
      self.field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'field must be a MocPhysicalPostShockFieldResult or None'
      )
    ####
    samples = tuple(self.upstream_samples)
    if any(
      not isinstance(sample, MocTransonicShockInterfaceSample)
      for sample in samples
    ):
      raise TypeError(
        'upstream_samples must contain MocTransonicShockInterfaceSample values'
      )
    ####
    object.__setattr__(self, 'upstream_samples', samples)
    if self.profile is not None and not isinstance(
      self.profile,
      MocTransonicShockInterfaceProfile,
    ):
      raise TypeError(
        'profile must be a MocTransonicShockInterfaceProfile or None'
      )
    ####
    if self.profile_build is not None and not isinstance(
      self.profile_build,
      MocTransonicShockInterfaceProfileBuildResult,
    ):
      raise TypeError(
        'profile_build must be a '
        'MocTransonicShockInterfaceProfileBuildResult or None'
      )
    ####
    for name in (
      'field_lineage_verified',
      'field_sampling_verified',
      'profile_build_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    audit = self.independent_measurement
    return bool(
      self.status is (
        MocTransonicShockInterfaceFieldProfileStatus
        .CONVERGED_FIELD_BOUND_PROFILE
      )
      and self.field is not None
      and self.profile is not None
      and self.profile_build is not None
      and self.field_lineage_verified
      and self.field_sampling_verified
      and self.profile_build_verified
      and self.profile_build.converged
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A field-bound interface does not close the downstream mixed regime."""

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
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': 'research-physical-field-bound-interface-profile-v1',
      'converged': self.converged,
      'field_lineage_verified': self.field_lineage_verified,
      'field_sampling_verified': self.field_sampling_verified,
      'profile_build_verified': self.profile_build_verified,
      'field_status': None if self.field is None else self.field.status.value,
      'upstream_samples': [
        sample.as_report() for sample in self.upstream_samples
      ],
      'profile': None if self.profile is None else self.profile.as_report(),
      'profile_build': (
        None if self.profile_build is None else self.profile_build.as_report()
      ),
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-physical-field-bound-transonic-interface; coupled '
        'pressure/tangency closure, refinement, shock-cell length, and external '
        'validation remain open'
      ),
      'request': self.request.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceRequest:
  """Inputs for carrying one verified placement across a shock interface."""

  placement: MocTransonicPlacementResult
  position_tolerance_m: float = 1.0e-9
  state_tolerance: float = 1.0e-6
  pressure_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(self.placement, MocTransonicPlacementResult):
      raise TypeError('placement must be a MocTransonicPlacementResult')
    ####
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = _finite(name, getattr(self, name))
      if value <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': TRANSONIC_INTERFACE_MODEL,
      'placement_status': self.placement.status.value,
      'placement_verified': self.placement.placement_verified,
      'frontier_kind': self.placement.request.frontier_kind.value,
      'frontier_fidelity': self.placement.request.frontier_fidelity.value,
      'frontier_source': self.placement.request.frontier_source,
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockInterfaceResult:
  """Audited upstream/downstream samples for one local shock interface."""

  status: MocTransonicShockInterfaceStatus
  request: MocTransonicShockInterfaceRequest
  upstream_sample: MocTransonicShockInterfaceSample | None = None
  downstream_sample: MocTransonicShockInterfaceSample | None = None
  shock_geometry: MocTransonicShockGeometryResult | None = None
  shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  upstream_state_residual: float | None = None
  frontier_state_residual: float | None = None
  upstream_pressure_residual: float | None = None
  frontier_pressure_residual: float | None = None
  independent_measurement: Any | None = None
  placement_verified: bool = False
  geometry_verified: bool = False
  upstream_lineage_verified: bool = False
  downstream_state_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicShockInterfaceStatus):
      raise TypeError('status must be a MocTransonicShockInterfaceStatus')
    ####
    if not isinstance(self.request, MocTransonicShockInterfaceRequest):
      raise TypeError('request must be a MocTransonicShockInterfaceRequest')
    ####
    for name in ('upstream_sample', 'downstream_sample'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocTransonicShockInterfaceSample,
      ):
        raise TypeError(
          f'{name} must be a MocTransonicShockInterfaceSample or None'
        )
      ####
    ####
    if (self.shock_geometry is None) != (self.shock_geometry_audit is None):
      raise ValueError(
        'shock_geometry and shock_geometry_audit must be supplied together'
      )
    ####
    if self.shock_geometry is not None and not isinstance(
      self.shock_geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError(
        'shock_geometry must be a MocTransonicShockGeometryResult or None'
      )
    ####
    if self.shock_geometry_audit is not None and not isinstance(
      self.shock_geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError(
        'shock_geometry_audit must be a MocTransonicShockGeometryAudit or None'
      )
    ####
    for name in (
      'upstream_state_residual',
      'frontier_state_residual',
      'upstream_pressure_residual',
      'frontier_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = _finite(name, value)
      if numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'placement_verified',
      'geometry_verified',
      'upstream_lineage_verified',
      'downstream_state_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    audit = self.independent_measurement
    return bool(
      self.status is MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE
      and self.placement_verified
      and self.geometry_verified
      and self.upstream_lineage_verified
      and self.downstream_state_verified
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def interface_verified(self) -> bool:
    return self.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A local interface does not close the surrounding mixed-regime field."""

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

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocTransonicShockInterfaceStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.converged
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'local transonic interface remains below mixed-regime closure and '
        'continued-chain promotion gates'
      ),
      diagnostics={
        'interface_status': self.status.value,
        'interface_verified': self.interface_verified,
        'placement_verified': self.placement_verified,
        'geometry_verified': self.geometry_verified,
        'upstream_lineage_verified': self.upstream_lineage_verified,
        'downstream_state_verified': self.downstream_state_verified,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'coupled-reflected-mixed-regime-field-and-independent-refinement-'
          'before-physical-shock-cell-promotion'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': TRANSONIC_INTERFACE_MODEL,
      'converged': self.converged,
      'interface_verified': self.interface_verified,
      'placement_verified': self.placement_verified,
      'geometry_verified': self.geometry_verified,
      'upstream_lineage_verified': self.upstream_lineage_verified,
      'downstream_state_verified': self.downstream_state_verified,
      'upstream_state_residual': self.upstream_state_residual,
      'frontier_state_residual': self.frontier_state_residual,
      'upstream_pressure_residual': self.upstream_pressure_residual,
      'frontier_pressure_residual': self.frontier_pressure_residual,
      'upstream_sample': (
        None
        if self.upstream_sample is None
        else self.upstream_sample.as_report()
      ),
      'downstream_sample': (
        None
        if self.downstream_sample is None
        else self.downstream_sample.as_report()
      ),
      'shock_geometry': (
        None if self.shock_geometry is None else self.shock_geometry.as_report()
      ),
      'shock_geometry_audit': (
        None
        if self.shock_geometry_audit is None
        else self.shock_geometry_audit.as_report()
      ),
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-solver-owned-transonic-interface; coupled reflected '
        'mixed-regime closure, physical shock-cell length, and external '
        'validation remain open'
      ),
      'request': self.request.as_report(),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocTransonicShockInterfaceStatus,
  request: MocTransonicShockInterfaceRequest,
  *,
  upstream_sample: MocTransonicShockInterfaceSample | None = None,
  downstream_sample: MocTransonicShockInterfaceSample | None = None,
  shock_geometry: MocTransonicShockGeometryResult | None = None,
  shock_geometry_audit: MocTransonicShockGeometryAudit | None = None,
  upstream_state_residual: float | None = None,
  frontier_state_residual: float | None = None,
  upstream_pressure_residual: float | None = None,
  frontier_pressure_residual: float | None = None,
  placement_verified: bool = False,
  geometry_verified: bool = False,
  upstream_lineage_verified: bool = False,
  downstream_state_verified: bool = False,
  message: str,
) -> MocTransonicShockInterfaceResult:
  return MocTransonicShockInterfaceResult(
    status=status,
    request=request,
    upstream_sample=upstream_sample,
    downstream_sample=downstream_sample,
    shock_geometry=shock_geometry,
    shock_geometry_audit=shock_geometry_audit,
    upstream_state_residual=upstream_state_residual,
    frontier_state_residual=frontier_state_residual,
    upstream_pressure_residual=upstream_pressure_residual,
    frontier_pressure_residual=frontier_pressure_residual,
    placement_verified=placement_verified,
    geometry_verified=geometry_verified,
    upstream_lineage_verified=upstream_lineage_verified,
    downstream_state_verified=downstream_state_verified,
    message=message,
  )
####


def solve_moc_transonic_shock_interface(
  request: MocTransonicShockInterfaceRequest,
) -> MocTransonicShockInterfaceResult:
  """Build and independently audit one local post-shock interface handoff."""

  if not isinstance(request, MocTransonicShockInterfaceRequest):
    raise TypeError('request must be a MocTransonicShockInterfaceRequest')
  ####
  placement = request.placement
  if not placement.placement_verified:
    return _failure(
      MocTransonicShockInterfaceStatus.PLACEMENT_REQUIRED,
      request,
      message=(
        'shock-interface handoff requires a verified bounded placement on a '
        'resolved planar-MOC frontier'
      ),
    )
  ####
  geometry = placement.shock_geometry
  geometry_audit = placement.shock_geometry_audit
  point = placement.intersection_point_m
  upstream_state = placement.transport_state
  frontier_state = placement.frontier_state
  upstream_pressure = placement.transport_total_pressure_Pa
  frontier_pressure = placement.frontier_total_pressure_Pa
  if geometry is None or geometry_audit is None or point is None:
    return _failure(
      MocTransonicShockInterfaceStatus.GEOMETRY_FAILURE,
      request,
      message='verified placement retained no complete scalar shock geometry',
    )
  ####
  if upstream_state is None or frontier_state is None:
    return _failure(
      MocTransonicShockInterfaceStatus.UPSTREAM_LINEAGE_FAILURE,
      request,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      message='verified placement retained no upstream and frontier states',
    )
  ####
  shock_state = geometry.request.shock_state
  expected_upstream = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=shock_state.upstream_flow_angle_rad,
    mach=shock_state.upstream_mach,
    gamma=shock_state.gamma,
  )
  upstream_state_residual = _state_residual(upstream_state, expected_upstream)
  frontier_state_residual = _state_residual(frontier_state, expected_upstream)
  upstream_pressure_residual = (
    None
    if upstream_pressure is None
    else _pressure_residual(
      upstream_pressure,
      shock_state.upstream_total_pressure_Pa,
    )
  )
  frontier_pressure_residual = (
    None
    if frontier_pressure is None
    else _pressure_residual(
      frontier_pressure,
      shock_state.upstream_total_pressure_Pa,
    )
  )
  upstream_lineage_verified = bool(
    upstream_state_residual <= request.state_tolerance
    and frontier_state_residual <= request.state_tolerance
    and upstream_pressure_residual is not None
    and frontier_pressure_residual is not None
    and upstream_pressure_residual <= request.pressure_tolerance
    and frontier_pressure_residual <= request.pressure_tolerance
  )
  if not upstream_lineage_verified:
    return _failure(
      MocTransonicShockInterfaceStatus.UPSTREAM_LINEAGE_FAILURE,
      request,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      upstream_state_residual=upstream_state_residual,
      frontier_state_residual=frontier_state_residual,
      upstream_pressure_residual=upstream_pressure_residual,
      frontier_pressure_residual=frontier_pressure_residual,
      placement_verified=True,
      geometry_verified=False,
      message=(
        'placed upstream and neighboring-frontier lineages do not reproduce '
        'the scalar shock upstream state and total pressure'
      ),
    )
  ####
  geometry_verified = bool(
    geometry.geometry_verified
    and geometry_audit.geometry_binding_verified
    and geometry_audit.converged
    and abs(geometry.shock_point_m[0] - point[0]) <= request.position_tolerance_m
    and abs(geometry.shock_point_m[1] - point[1]) <= request.position_tolerance_m
  )
  if not geometry_verified:
    return _failure(
      MocTransonicShockInterfaceStatus.GEOMETRY_FAILURE,
      request,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      upstream_state_residual=upstream_state_residual,
      frontier_state_residual=frontier_state_residual,
      upstream_pressure_residual=upstream_pressure_residual,
      frontier_pressure_residual=frontier_pressure_residual,
      placement_verified=True,
      upstream_lineage_verified=True,
      message='placed scalar shock geometry did not pass its independent audit',
    )
  ####
  downstream_sample = MocTransonicShockInterfaceSample(
    point_m=point,
    mach=shock_state.downstream_mach,
    flow_angle_rad=shock_state.upstream_flow_angle_rad,
    static_pressure_Pa=shock_state.downstream_static_pressure_Pa,
    total_pressure_Pa=shock_state.downstream_total_pressure_Pa,
    gamma=shock_state.gamma,
  )
  upstream_sample = MocTransonicShockInterfaceSample(
    point_m=point,
    mach=shock_state.upstream_mach,
    flow_angle_rad=shock_state.upstream_flow_angle_rad,
    static_pressure_Pa=shock_state.upstream_static_pressure_Pa,
    total_pressure_Pa=shock_state.upstream_total_pressure_Pa,
    gamma=shock_state.gamma,
  )
  downstream_state_verified = bool(
    downstream_sample.mach < 1.0
    and shock_state.downstream_subsonic
    and shock_state.upstream_supersonic
    and 0.0 < shock_state.total_pressure_ratio < 1.0
  )
  if not downstream_state_verified:
    return _failure(
      MocTransonicShockInterfaceStatus.DOWNSTREAM_STATE_FAILURE,
      request,
      upstream_sample=upstream_sample,
      downstream_sample=downstream_sample,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      upstream_state_residual=upstream_state_residual,
      frontier_state_residual=frontier_state_residual,
      upstream_pressure_residual=upstream_pressure_residual,
      frontier_pressure_residual=frontier_pressure_residual,
      placement_verified=True,
      geometry_verified=True,
      upstream_lineage_verified=True,
      message='scalar shock state did not retain a physical subsonic downstream branch',
    )
  ####
  result = MocTransonicShockInterfaceResult(
    status=MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE,
    request=request,
    upstream_sample=upstream_sample,
    downstream_sample=downstream_sample,
    shock_geometry=geometry,
    shock_geometry_audit=geometry_audit,
    upstream_state_residual=upstream_state_residual,
    frontier_state_residual=frontier_state_residual,
    upstream_pressure_residual=upstream_pressure_residual,
    frontier_pressure_residual=frontier_pressure_residual,
    placement_verified=True,
    geometry_verified=True,
    upstream_lineage_verified=True,
    downstream_state_verified=True,
    message=(
      'solver-owned bounded placement now carries audited upstream and '
      'downstream shock-interface samples; coupled mixed-regime closure '
      'remains open'
    ),
  )
  try:
    from exhaust_plume.validation.moc_transonic_interface import (
      measure_moc_transonic_shock_interface,
    )

    audit = measure_moc_transonic_shock_interface(result)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocTransonicShockInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      upstream_sample=upstream_sample,
      downstream_sample=downstream_sample,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      upstream_state_residual=upstream_state_residual,
      frontier_state_residual=frontier_state_residual,
      upstream_pressure_residual=upstream_pressure_residual,
      frontier_pressure_residual=frontier_pressure_residual,
      placement_verified=True,
      geometry_verified=True,
      upstream_lineage_verified=True,
      downstream_state_verified=True,
      message=f'independent shock-interface audit raised: {error}',
    )
  ####
  if not audit.converged:
    result = MocTransonicShockInterfaceResult(
      status=MocTransonicShockInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
      request=request,
      upstream_sample=upstream_sample,
      downstream_sample=downstream_sample,
      shock_geometry=geometry,
      shock_geometry_audit=geometry_audit,
      upstream_state_residual=upstream_state_residual,
      frontier_state_residual=frontier_state_residual,
      upstream_pressure_residual=upstream_pressure_residual,
      frontier_pressure_residual=frontier_pressure_residual,
      placement_verified=True,
      geometry_verified=True,
      upstream_lineage_verified=True,
      downstream_state_verified=True,
      independent_measurement=audit,
      message=(
        'shock-interface samples were built, but their independent audit '
        f'did not pass: {audit.message}'
      ),
    )
    return result
  ####
  return MocTransonicShockInterfaceResult(
    status=MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE,
    request=request,
    upstream_sample=upstream_sample,
    downstream_sample=downstream_sample,
    shock_geometry=geometry,
    shock_geometry_audit=geometry_audit,
    upstream_state_residual=upstream_state_residual,
    frontier_state_residual=frontier_state_residual,
    upstream_pressure_residual=upstream_pressure_residual,
    frontier_pressure_residual=frontier_pressure_residual,
    independent_measurement=audit,
    placement_verified=True,
    geometry_verified=True,
    upstream_lineage_verified=True,
    downstream_state_verified=True,
    message=(
      'bounded shock interface, scalar conservation geometry, state lineage, '
      'and independent handoff audit passed; global mixed-regime closure '
      'remains pending'
    ),
  )
####


def _profile_build_failure(
  status: MocTransonicShockInterfaceProfileBuildStatus,
  request: MocTransonicShockInterfaceProfileRequest,
  *,
  profile: MocTransonicShockInterfaceProfile | None = None,
  independent_measurement: Any | None = None,
  upstream_profile_verified: bool = False,
  normal_alignment_verified: bool = False,
  downstream_state_verified: bool = False,
  message: str,
) -> MocTransonicShockInterfaceProfileBuildResult:
  return MocTransonicShockInterfaceProfileBuildResult(
    status=status,
    request=request,
    profile=profile,
    independent_measurement=independent_measurement,
    upstream_profile_verified=upstream_profile_verified,
    normal_alignment_verified=normal_alignment_verified,
    downstream_state_verified=downstream_state_verified,
    message=message,
  )
####


def build_moc_transonic_shock_interface_profile(
  request: MocTransonicShockInterfaceProfileRequest,
) -> MocTransonicShockInterfaceProfileBuildResult:
  """Derive and audit a cross-section normal-shock profile.

  This is deliberately a profile builder, not an interface-placement solver.
  It accepts only caller-owned upstream samples that already lie on a common
  ordered cross-section and derives each downstream state with the exact
  calorically-perfect normal-shock primitive.  The returned profile remains a
  research handoff for the coupled field.
  """

  if not isinstance(request, MocTransonicShockInterfaceProfileRequest):
    raise TypeError(
      'request must be a MocTransonicShockInterfaceProfileRequest'
    )
  ####
  upstream = request.upstream_samples
  if len(upstream) < 2:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message='normal-shock profile requires at least two upstream samples',
    )
  ####
  x_reference = upstream[0].point_m[0]
  if any(
    abs(sample.point_m[0] - x_reference) > request.position_tolerance_m
    for sample in upstream[1:]
  ):
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message='upstream samples must lie on one cross-section x',
    )
  ####
  if any(
    second.point_m[1] <= first.point_m[1] + request.position_tolerance_m
    for first, second in zip(upstream, upstream[1:])
  ):
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message='upstream sample ordinates must be strictly increasing',
    )
  ####
  if any(sample.mach <= 1.0 for sample in upstream):
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message='normal-shock profile upstream samples must be supersonic',
    )
  ####
  gamma = upstream[0].gamma
  if any(
    abs(sample.gamma - gamma) > request.state_tolerance
    for sample in upstream[1:]
  ):
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message='normal-shock profile upstream samples must use one gamma',
    )
  ####
  thermodynamics_verified = all(
    _pressure_residual(
      sample.static_pressure_Pa,
      _sample_static_pressure(sample),
    ) <= request.pressure_tolerance
    for sample in upstream
  )
  if not thermodynamics_verified:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.UPSTREAM_PROFILE_FAILURE,
      request,
      message=(
        'upstream samples do not reproduce static pressure from their '
        'reported total pressure and Mach number'
      ),
    )
  ####
  normal_alignment_verified = all(
    _line_angle_residual(
      sample.flow_angle_rad,
      request.interface_normal_angle_rad,
    ) <= request.normal_alignment_tolerance_rad
    for sample in upstream
  )
  if not normal_alignment_verified:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.NORMAL_ALIGNMENT_FAILURE,
      request,
      upstream_profile_verified=True,
      message=(
        'normal-shock profile requires every upstream flow direction to align '
        'with the retained interface normal'
      ),
    )
  ####
  downstream = tuple(
    _normal_shock_profile_sample(sample, request) for sample in upstream
  )
  if any(sample is None for sample in downstream):
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.SHOCK_STATE_FAILURE,
      request,
      upstream_profile_verified=True,
      normal_alignment_verified=True,
      message='normal-shock primitive did not produce a complete subsonic state',
    )
  ####
  downstream_samples = tuple(
    sample for sample in downstream if sample is not None
  )
  try:
    profile = MocTransonicShockInterfaceProfile(
      upstream_samples=upstream,
      downstream_samples=downstream_samples,
      interface_normal_angle_rad=request.interface_normal_angle_rad,
      profile_id=request.profile_id,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.state_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  except (TypeError, ValueError) as error:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.SHOCK_STATE_FAILURE,
      request,
      upstream_profile_verified=True,
      normal_alignment_verified=True,
      message=f'normal-shock profile construction failed: {error}',
    )
  ####
  result = MocTransonicShockInterfaceProfileBuildResult(
    status=(
      MocTransonicShockInterfaceProfileBuildStatus
      .CONVERGED_NORMAL_SHOCK_PROFILE
    ),
    request=request,
    profile=profile,
    upstream_profile_verified=True,
    normal_alignment_verified=True,
    downstream_state_verified=True,
    message=(
      'solver-owned normal-shock cross-section profile was derived from an '
      'ordered upstream sample set; mixed-regime closure remains open'
    ),
  )
  try:
    from exhaust_plume.validation.moc_transonic_interface import (
      measure_moc_transonic_shock_interface_profile_build,
    )

    audit = measure_moc_transonic_shock_interface_profile_build(result)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      profile=profile,
      upstream_profile_verified=True,
      normal_alignment_verified=True,
      downstream_state_verified=True,
      message=f'independent normal-shock profile audit raised: {error}',
    )
  ####
  if not audit.converged:
    return _profile_build_failure(
      MocTransonicShockInterfaceProfileBuildStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      profile=profile,
      independent_measurement=audit,
      upstream_profile_verified=True,
      normal_alignment_verified=True,
      downstream_state_verified=True,
      message=(
        'normal-shock profile was built, but its independent audit did not '
        f'pass: {audit.message}'
      ),
    )
  ####
  return MocTransonicShockInterfaceProfileBuildResult(
    status=(
      MocTransonicShockInterfaceProfileBuildStatus
      .CONVERGED_NORMAL_SHOCK_PROFILE
    ),
    request=request,
    profile=profile,
    independent_measurement=audit,
    upstream_profile_verified=True,
    normal_alignment_verified=True,
    downstream_state_verified=True,
    message=(
      'normal-shock profile construction and independent rederivation passed; '
      'global mixed-regime closure remains pending'
    ),
  )
####


def _field_profile_failure(
  status: MocTransonicShockInterfaceFieldProfileStatus,
  request: MocTransonicShockInterfaceFieldProfileRequest,
  *,
  field: MocPhysicalPostShockFieldResult | None = None,
  upstream_samples: tuple[MocTransonicShockInterfaceSample, ...] = (),
  profile: MocTransonicShockInterfaceProfile | None = None,
  profile_build: MocTransonicShockInterfaceProfileBuildResult | None = None,
  independent_measurement: Any | None = None,
  field_lineage_verified: bool = False,
  field_sampling_verified: bool = False,
  profile_build_verified: bool = False,
  message: str,
) -> MocTransonicShockInterfaceFieldProfileResult:
  return MocTransonicShockInterfaceFieldProfileResult(
    status=status,
    request=request,
    field=field,
    upstream_samples=upstream_samples,
    profile=profile,
    profile_build=profile_build,
    independent_measurement=independent_measurement,
    field_lineage_verified=field_lineage_verified,
    field_sampling_verified=field_sampling_verified,
    profile_build_verified=profile_build_verified,
    message=message,
  )
####


def build_moc_transonic_shock_interface_profile_from_field(
  request: MocTransonicShockInterfaceFieldProfileRequest,
) -> MocTransonicShockInterfaceFieldProfileResult:
  """Bind a normal-shock profile to exact samples of a physical field.

  The field supplies the upstream state and total-pressure lineage at every
  requested point.  No state is projected, extrapolated, or replaced by the
  scalar frontier diagnostic.  The normal-shock profile builder then derives
  the downstream samples and retains its own independent audit.
  """

  if not isinstance(request, MocTransonicShockInterfaceFieldProfileRequest):
    raise TypeError(
      'request must be a MocTransonicShockInterfaceFieldProfileRequest'
    )
  ####
  field = request.field
  field_lineage_verified = bool(
    field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
  )
  if not field_lineage_verified:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.FIELD_SAMPLING_UNAVAILABLE,
      request,
      field=field,
      field_lineage_verified=False,
      message=(
        'field-bound interface sampling requires a converged physical field '
        'with physical closure and state sampling available'
      ),
    )
  ####
  points = request.sample_points_m
  if len(points) < 2:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.CROSS_SECTION_FAILURE,
      request,
      field=field,
      field_lineage_verified=True,
      message='field-bound interface profile requires at least two sample points',
    )
  ####
  x_reference = points[0][0]
  if any(
    abs(point[0] - x_reference) > request.position_tolerance_m
    for point in points[1:]
  ):
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.CROSS_SECTION_FAILURE,
      request,
      field=field,
      field_lineage_verified=True,
      message='field-bound interface sample points must lie on one cross-section x',
    )
  ####
  if any(
    second[1] <= first[1] + request.position_tolerance_m
    for first, second in zip(points, points[1:])
  ):
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.CROSS_SECTION_FAILURE,
      request,
      field=field,
      field_lineage_verified=True,
      message='field-bound interface sample ordinates must be strictly increasing',
    )
  ####
  upstream_samples: list[MocTransonicShockInterfaceSample] = []
  try:
    for point in points:
      state = field.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      total_pressure = field.total_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      if state is None or total_pressure is None:
        return _field_profile_failure(
          MocTransonicShockInterfaceFieldProfileStatus.FIELD_SAMPLE_FAILURE,
          request,
          field=field,
          upstream_samples=tuple(upstream_samples),
          field_lineage_verified=True,
          message=(
            'physical field sampler returned no state and total-pressure pair '
            f'at cross-section point {point}'
          ),
        )
      ####
      static_pressure = _static_pressure_from_state_total_pressure(
        state,
        total_pressure,
      )
      upstream_samples.append(
        MocTransonicShockInterfaceSample(
          point_m=point,
          mach=state.mach,
          flow_angle_rad=state.theta_rad,
          static_pressure_Pa=static_pressure,
          total_pressure_Pa=total_pressure,
          gamma=state.gamma,
        )
      )
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.FIELD_SAMPLE_FAILURE,
      request,
      field=field,
      upstream_samples=tuple(upstream_samples),
      field_lineage_verified=True,
      message=f'physical field sampling raised: {error}',
    )
  ####
  samples = tuple(upstream_samples)
  profile_build = build_moc_transonic_shock_interface_profile(
    MocTransonicShockInterfaceProfileRequest(
      upstream_samples=samples,
      interface_normal_angle_rad=request.interface_normal_angle_rad,
      profile_id=request.profile_id,
      normal_alignment_tolerance_rad=request.normal_alignment_tolerance_rad,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.state_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  )
  if not profile_build.converged or profile_build.profile is None:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.PROFILE_BUILD_FAILURE,
      request,
      field=field,
      upstream_samples=samples,
      profile=profile_build.profile,
      profile_build=profile_build,
      field_lineage_verified=True,
      field_sampling_verified=True,
      profile_build_verified=False,
      message=(
        'field samples were retained, but the normal-shock profile builder '
        f'did not converge: {profile_build.message}'
      ),
    )
  ####
  result = MocTransonicShockInterfaceFieldProfileResult(
    status=(
      MocTransonicShockInterfaceFieldProfileStatus
      .CONVERGED_FIELD_BOUND_PROFILE
    ),
    request=request,
    field=field,
    upstream_samples=samples,
    profile=profile_build.profile,
    profile_build=profile_build,
    field_lineage_verified=True,
    field_sampling_verified=True,
    profile_build_verified=True,
    message=(
      'normal-shock profile was derived from retained physical-field samples; '
      'coupled pressure/tangency closure remains open'
    ),
  )
  try:
    from exhaust_plume.validation.moc_transonic_interface import (
      measure_moc_transonic_shock_interface_profile_from_field,
    )

    audit = measure_moc_transonic_shock_interface_profile_from_field(result)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      upstream_samples=samples,
      profile=profile_build.profile,
      profile_build=profile_build,
      field_lineage_verified=True,
      field_sampling_verified=True,
      profile_build_verified=True,
      message=f'independent field-bound profile audit raised: {error}',
    )
  ####
  if not audit.converged:
    return _field_profile_failure(
      MocTransonicShockInterfaceFieldProfileStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      field=field,
      upstream_samples=samples,
      profile=profile_build.profile,
      profile_build=profile_build,
      independent_measurement=audit,
      field_lineage_verified=True,
      field_sampling_verified=True,
      profile_build_verified=True,
      message=(
        'field-bound profile was built, but its independent audit did not '
        f'pass: {audit.message}'
      ),
    )
  ####
  return MocTransonicShockInterfaceFieldProfileResult(
    status=(
      MocTransonicShockInterfaceFieldProfileStatus
      .CONVERGED_FIELD_BOUND_PROFILE
    ),
    request=request,
    field=field,
    upstream_samples=samples,
    profile=profile_build.profile,
    profile_build=profile_build,
    independent_measurement=audit,
    field_lineage_verified=True,
    field_sampling_verified=True,
    profile_build_verified=True,
    message=(
      'physical-field sample lineage and normal-shock profile rederivation '
      'passed; global mixed-regime closure remains pending'
    ),
  )
####
