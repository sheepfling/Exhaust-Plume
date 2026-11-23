"""Lossless lifecycle and negotiation adapters for the 0.1.x compatibility API.

The canonical runtime lifecycle is the typed ``contracts.lifecycle_v1``
dispatcher exposed through :mod:`exhaust_plume.api.v1`.  The first alpha also
shipped a UUID-oriented ``api.lifecycle`` witness with a string capability
request.  These adapters translate the lifecycle shell and typed negotiation
without changing serialized v1 product fields.  A review-witness result still
requires an explicit product adapter; it is never silently treated as a v1
wire result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from exhaust_plume.api.errors import PlumeApiError, PlumeErrorCode
from exhaust_plume.api.contracts import (
  Applicability as LegacyApplicability,
  FrameRef as LegacyFrameRef,
  PlumeFluxSection as LegacyPlumeFluxSection,
  Pose3 as LegacyPose3,
  Provenance as LegacyProvenance,
  SpeciesMassFlow as LegacySpeciesMassFlow,
)
from exhaust_plume.api.lifecycle import (
  PlumeSession as LegacyPlumeSession,
  PlumeSnapshot as LegacyPlumeSnapshot,
  ProductRequest as LegacyProductRequest,
  SnapshotRequest as LegacySnapshotRequest,
)
from exhaust_plume.contracts.common_v1 import (
  ApiError,
  ApiModel,
  CapabilityIdentity,
  ErrorCode,
  Pose,
)
from exhaust_plume.contracts.errors import (
  ContractViolationError,
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
)
from exhaust_plume.contracts.lifecycle_v1 import (
  CapabilitySpec,
  ProductSession,
  ProductSnapshot,
)
from exhaust_plume.contracts.handoff_v1 import (
  HandoffApplicabilityV1,
  HandoffFrameV1,
  HandoffPoseV1,
  HandoffProvenanceV1,
  HandoffSpeciesMassFlowV1,
  PlumeFluxSectionV1,
)
from exhaust_plume.contracts.specs_v1 import get_product_capability_spec


def canonical_capability_from_legacy_request(request: LegacyProductRequest) -> CapabilityIdentity:
  """Translate a legacy string request into the canonical typed identity."""

  identity = CapabilityIdentity.parse(request.capability_id)
  schema_major_text = request.schema_version.split('.', 1)[0]
  if int(schema_major_text) != identity.major:
    raise UnsupportedProductVersionError(
      f'capability {identity.wire_id} and schema {request.schema_version} have different majors'
    )
  ####
  return identity
####


def legacy_request_from_capability(
    capability: CapabilityIdentity | CapabilitySpec[Any, Any],
    *,
    schema_version: str | None = None,
) -> LegacyProductRequest:
  """Translate a canonical capability/spec into the alpha request envelope."""

  identity = capability.capability if isinstance(capability, CapabilitySpec) else capability
  return LegacyProductRequest(
    capability_id=identity.wire_id,
    schema_version=schema_version or f'{identity.major}.0.0',
  )
####


def canonical_spec_from_legacy_request(
    request: LegacyProductRequest,
) -> CapabilitySpec[Any, Any]:
  """Resolve a legacy request through the one canonical v1 product registry."""

  return get_product_capability_spec(canonical_capability_from_legacy_request(request))
####


def plume_flux_section_v1_from_legacy(section: LegacyPlumeFluxSection) -> PlumeFluxSectionV1:
  """Adapt representable legacy flux fields without conflating energy terms.

  The legacy ``total_energy_flow_W`` value is retained under that exact name;
  stagnation enthalpy and characteristic radius remain absent because the
  legacy payload does not define them. Inputs that fail the canonical species
  or pressure-thrust closure are rejected by the v1 model.
  """

  pressure_thrust = tuple(
    (section.pressure_Pa - section.ambient_pressure_Pa) * section.area_m2 * component
    for component in section.normal
  )
  advective = tuple(total - thrust for total, thrust in zip(section.momentum_flux_N, pressure_thrust, strict=True))
  return PlumeFluxSectionV1(
    time_s=section.time_s,
    frame=HandoffFrameV1(
      frame_id=section.frame.frame_id,
      parent_frame_id=section.frame.parent_frame_id,
      pose_parent_from_frame=HandoffPoseV1(
        translation_m=section.frame.pose_parent_from_frame.translation_m,
        rotation_xyzw=section.frame.pose_parent_from_frame.rotation_xyzw,
      ),
    ),
    section_pose=HandoffPoseV1(
      translation_m=section.section_pose.translation_m,
      rotation_xyzw=section.section_pose.rotation_xyzw,
    ),
    center_m=section.section_pose.translation_m,
    normal=section.normal,
    area_m2=section.area_m2,
    mass_flow_kg_s=section.mass_flow_kgps,
    momentum_flux_N=section.momentum_flux_N,
    advective_momentum_flux_N=advective,
    pressure_thrust_N=pressure_thrust,
    total_energy_flow_W=section.total_energy_flow_W,
    stagnation_enthalpy_flux_W=None,
    species_mass_flows_kg_s=tuple(
      HandoffSpeciesMassFlowV1(species_id=item.species_id, mass_flow_kg_s=item.mass_flow_kgps)
      for item in section.species_mass_flows_kgps
    ),
    pressure_Pa=section.pressure_Pa,
    ambient_pressure_Pa=section.ambient_pressure_Pa,
    pressure_match_relative_residual=section.pressure_match_relative_residual,
    cross_section_second_moment_m2=section.cross_section_second_moment_m2,
    characteristic_radius_m=None,
    provenance=HandoffProvenanceV1(
      model_id=section.provenance.model_id,
      model_version=section.provenance.model_version,
      code_revision=section.provenance.code_revision,
      configuration_sha256=section.provenance.configuration_sha256,
      asset_digests_sha256=section.provenance.asset_digests_sha256,
    ),
    applicability=HandoffApplicabilityV1(
      supported=section.applicability.supported,
      domain=section.applicability.domain,
      violations=section.applicability.violations,
    ),
    uncertainty=section.uncertainty,
  )
####


def plume_flux_section_v1_to_legacy(section: PlumeFluxSectionV1) -> LegacyPlumeFluxSection:
  """Return a legacy DTO only when no canonical-only value would be lost."""

  if section.stagnation_enthalpy_flux_W is not None:
    raise ValueError('legacy flux DTO cannot preserve stagnation_enthalpy_flux_W')
  if section.characteristic_radius_m is not None:
    raise ValueError('legacy flux DTO cannot preserve characteristic_radius_m')
  if section.provenance.producer_metadata:
    raise ValueError('legacy flux DTO cannot preserve provenance producer_metadata')
  if section.total_energy_flow_W is None:
    raise ValueError('legacy flux DTO requires its separately named total_energy_flow_W')
  ####
  return LegacyPlumeFluxSection(
    time_s=section.time_s,
    frame=LegacyFrameRef(
      frame_id=section.frame.frame_id,
      parent_frame_id=section.frame.parent_frame_id,
      pose_parent_from_frame=LegacyPose3(
        translation_m=section.frame.pose_parent_from_frame.translation_m,
        rotation_xyzw=section.frame.pose_parent_from_frame.rotation_xyzw,
      ),
    ),
    section_pose=LegacyPose3(
      translation_m=section.section_pose.translation_m,
      rotation_xyzw=section.section_pose.rotation_xyzw,
    ),
    normal=section.normal,
    area_m2=section.area_m2,
    mass_flow_kgps=section.mass_flow_kg_s,
    momentum_flux_N=section.momentum_flux_N,
    total_energy_flow_W=section.total_energy_flow_W,
    species_mass_flows_kgps=tuple(
      LegacySpeciesMassFlow(species_id=item.species_id, mass_flow_kgps=item.mass_flow_kg_s)
      for item in section.species_mass_flows_kg_s
    ),
    pressure_Pa=section.pressure_Pa,
    ambient_pressure_Pa=section.ambient_pressure_Pa,
    pressure_match_relative_residual=section.pressure_match_relative_residual,
    cross_section_second_moment_m2=section.cross_section_second_moment_m2,
    provenance=LegacyProvenance(
      model_id=section.provenance.model_id,
      model_version=section.provenance.model_version,
      code_revision=section.provenance.code_revision,
      configuration_sha256=section.provenance.configuration_sha256,
      asset_digests_sha256=section.provenance.asset_digests_sha256,
    ),
    applicability=LegacyApplicability(
      supported=section.applicability.supported,
      domain=section.applicability.domain,
      violations=section.applicability.violations,
    ),
    uncertainty=section.uncertainty,
  )
####


@dataclass(frozen=True, slots=True)
class CanonicalSnapshotLegacyAdapter:
  """Expose a canonical snapshot through the legacy ``get_product`` shell.

  The old request envelope carries no typed product payload, so callers bind
  one canonical request per capability when constructing this adapter. The
  returned object is the canonical v1 result, preserving its class identity
  and serialized fields.
  """

  snapshot: ProductSnapshot
  bound_requests: Mapping[str, tuple[CapabilitySpec[Any, Any], ApiModel]]

  def __post_init__(self) -> None:
    object.__setattr__(self, 'bound_requests', dict(self.bound_requests))
  ####

  def get_product(self, request: LegacyProductRequest) -> ApiModel:
    identity = canonical_capability_from_legacy_request(request)
    try:
      capability_spec, typed_request = self.bound_requests[identity.wire_id]
    except KeyError as error:
      raise UnsupportedProductCapabilityError(
        f'no bound canonical request for {identity.wire_id}'
      ) from error
    ####
    if capability_spec.capability != identity:
      raise ContractViolationError(
        f'bound capability {capability_spec.capability.wire_id} does not match {identity.wire_id}'
      )
    ####
    return self.snapshot.evaluate(capability_spec, typed_request)
  ####
####


@dataclass(frozen=True, slots=True)
class LegacySnapshotCanonicalAdapter:
  """Expose a legacy snapshot through the canonical typed dispatcher.

  ``result_adapters`` must be supplied for review-witness DTOs. For a result
  that is already a canonical v1 model, ``lambda value: value`` is sufficient
  and preserves class identity.
  """

  snapshot: LegacyPlumeSnapshot
  supported_capabilities: tuple[CapabilityIdentity, ...]
  result_adapters: Mapping[str, Callable[[object], ApiModel]]

  def __post_init__(self) -> None:
    identities = tuple(capability.wire_id for capability in self.supported_capabilities)
    if len(identities) != len(set(identities)):
      raise ValueError('supported capability identities must be unique')
    ####
    object.__setattr__(self, 'supported_capabilities', tuple(self.supported_capabilities))
    object.__setattr__(self, 'result_adapters', dict(self.result_adapters))
  ####

  def supports(self, capability: CapabilityIdentity) -> bool:
    return capability in self.supported_capabilities
  ####

  def evaluate(self, capability: CapabilitySpec[Any, Any], request: ApiModel) -> ApiModel:
    if not self.supports(capability.capability):
      if any(candidate.name == capability.capability.name for candidate in self.supported_capabilities):
        raise UnsupportedProductVersionError(
          f'unsupported major version for {capability.capability.name}: {capability.capability.major}'
        )
      ####
      raise UnsupportedProductCapabilityError(
        f'unsupported capability: {capability.capability.wire_id}'
      )
    ####
    try:
      adapter = self.result_adapters[capability.capability.wire_id]
    except KeyError as error:
      raise ContractViolationError(
        f'no result adapter registered for {capability.capability.wire_id}'
      ) from error
    ####
    raw_result = self.snapshot.get_product(legacy_request_from_capability(capability))
    result = adapter(raw_result)
    if not isinstance(result, capability.result_type):
      raise ContractViolationError(
        f'legacy result adapter returned {type(result).__name__}; '
        f'expected {capability.result_type.__name__}'
      )
    ####
    del request
    return result
  ####
####


@dataclass(frozen=True, slots=True)
class CanonicalSessionLegacyAdapter:
  """Expose a canonical session through the old ``snapshot`` method."""

  session: ProductSession
  source_pose: Pose
  dynamic_state: Mapping[str, Any]
  ambient_state: Mapping[str, Any]
  bound_requests: Mapping[str, tuple[CapabilitySpec[Any, Any], ApiModel]]

  def snapshot(self, request: LegacySnapshotRequest) -> CanonicalSnapshotLegacyAdapter:
    snapshot = self.session.create_snapshot(
      time_s=request.time_s,
      source_pose=self.source_pose,
      dynamic_state=self.dynamic_state,
      ambient_state=self.ambient_state,
    )
    return CanonicalSnapshotLegacyAdapter(snapshot=snapshot, bound_requests=self.bound_requests)
  ####
####


@dataclass(frozen=True, slots=True)
class LegacySessionCanonicalAdapter:
  """Expose a legacy session through the canonical ``create_snapshot`` name."""

  session: LegacyPlumeSession
  supported_capabilities: tuple[CapabilityIdentity, ...]
  result_adapters: Mapping[str, Callable[[object], ApiModel]]

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: Pose,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> LegacySnapshotCanonicalAdapter:
    del source_pose, dynamic_state, ambient_state
    snapshot = self.session.snapshot(LegacySnapshotRequest(time_s=time_s))
    return LegacySnapshotCanonicalAdapter(
      snapshot=snapshot,
      supported_capabilities=self.supported_capabilities,
      result_adapters=self.result_adapters,
    )
  ####
####


_LEGACY_TO_CANONICAL_ERROR: Mapping[PlumeErrorCode, ErrorCode] = {
  PlumeErrorCode.CAPABILITY_NOT_SUPPORTED: ErrorCode.UNSUPPORTED_CAPABILITY,
  PlumeErrorCode.SCHEMA_VERSION_NOT_SUPPORTED: ErrorCode.UNSUPPORTED_MAJOR_VERSION,
  PlumeErrorCode.INVALID_REQUEST: ErrorCode.INVALID_REQUEST,
  PlumeErrorCode.INVALID_FRAME: ErrorCode.INVALID_REQUEST,
  PlumeErrorCode.INVALID_UNITS: ErrorCode.INVALID_REQUEST,
  PlumeErrorCode.TIME_OUT_OF_RANGE: ErrorCode.OUTSIDE_APPLICABILITY,
  PlumeErrorCode.EXTRAPOLATION_FORBIDDEN: ErrorCode.OUTSIDE_APPLICABILITY,
  PlumeErrorCode.OUT_OF_DOMAIN: ErrorCode.OUTSIDE_APPLICABILITY,
  PlumeErrorCode.APPLICABILITY_VIOLATION: ErrorCode.OUTSIDE_APPLICABILITY,
  PlumeErrorCode.NONPHYSICAL_STATE: ErrorCode.INVALID_PROVIDER_STATE,
  PlumeErrorCode.NUMERICAL_FAILURE: ErrorCode.BACKEND_FAILURE,
  PlumeErrorCode.RESOURCE_LIMIT: ErrorCode.RESOURCE_EXHAUSTED,
  PlumeErrorCode.INTERNAL_ERROR: ErrorCode.BACKEND_FAILURE,
}

_CANONICAL_TO_LEGACY_ERROR: Mapping[ErrorCode, PlumeErrorCode] = {
  ErrorCode.UNSUPPORTED_CAPABILITY: PlumeErrorCode.CAPABILITY_NOT_SUPPORTED,
  ErrorCode.UNSUPPORTED_MAJOR_VERSION: PlumeErrorCode.SCHEMA_VERSION_NOT_SUPPORTED,
  ErrorCode.INVALID_REQUEST: PlumeErrorCode.INVALID_REQUEST,
  ErrorCode.OUTSIDE_APPLICABILITY: PlumeErrorCode.OUT_OF_DOMAIN,
  ErrorCode.INVALID_PROVIDER_STATE: PlumeErrorCode.NONPHYSICAL_STATE,
  ErrorCode.SNAPSHOT_EXPIRED: PlumeErrorCode.TIME_OUT_OF_RANGE,
  ErrorCode.RESOURCE_EXHAUSTED: PlumeErrorCode.RESOURCE_LIMIT,
  ErrorCode.BACKEND_FAILURE: PlumeErrorCode.NUMERICAL_FAILURE,
  ErrorCode.CANCELLED: PlumeErrorCode.INVALID_REQUEST,
}


def canonical_error_from_legacy(error: PlumeApiError) -> ApiError:
  """Map a legacy exception to the canonical serializable error envelope."""

  details = dict(error.details)
  if error.session_id is not None:
    details.setdefault('session_id', str(error.session_id))
  ####
  return ApiError(
    code=_LEGACY_TO_CANONICAL_ERROR[error.code],
    message=error.message,
    details=details,
    retryable=error.code in {PlumeErrorCode.RESOURCE_LIMIT, PlumeErrorCode.NUMERICAL_FAILURE},
    provider_id=None if error.provider_id is None else str(error.provider_id),
    snapshot_id=None if error.snapshot_id is None else str(error.snapshot_id),
  )
####


def legacy_error_from_canonical(
    error: ApiError,
    *,
    session_id: str | None = None,
) -> PlumeApiError:
  """Map a canonical error envelope to the legacy structured exception."""

  details = dict(error.details)
  resolved_session_id = session_id or details.pop('session_id', None)
  return PlumeApiError(
    _CANONICAL_TO_LEGACY_ERROR[error.code],
    error.message,
    details=details,
    provider_id=None if error.provider_id is None else _uuid_or_none(error.provider_id),
    session_id=None if resolved_session_id is None else _uuid_or_none(resolved_session_id),
    snapshot_id=None if error.snapshot_id is None else _uuid_or_none(error.snapshot_id),
  )
####


def _uuid_or_none(value: str) -> Any:
  from uuid import UUID

  try:
    return UUID(value)
  except (ValueError, AttributeError):
    return None
  ####
####


__all__ = (
  'CanonicalSessionLegacyAdapter',
  'CanonicalSnapshotLegacyAdapter',
  'LegacySessionCanonicalAdapter',
  'LegacySnapshotCanonicalAdapter',
  'canonical_capability_from_legacy_request',
  'canonical_error_from_legacy',
  'canonical_spec_from_legacy_request',
  'legacy_error_from_canonical',
  'legacy_request_from_capability',
  'plume_flux_section_v1_from_legacy',
  'plume_flux_section_v1_to_legacy',
)
