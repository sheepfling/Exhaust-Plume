"""Static prescribed provider for the first sectioned-tube MVP slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from exhaust_plume.api.capabilities import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.api.contracts import (
    Applicability,
    FidelityClaim,
    FrameRef,
    ModelFidelity,
    ProductResult,
    Provenance,
    ResultEnvelope,
    ResultStatus,
    SectionedTubePayload,
    SectionedTubeResult,
    SnapshotRequest,
    ValidationLevel,
    calculate_content_sha256,
)
from exhaust_plume.api.errors import PlumeApiError, PlumeErrorCode
from exhaust_plume.api.lifecycle import (
  CapabilityAdvertisement,
  ProductRequest,
  ProviderDescriptor,
)
from exhaust_plume.api.v1 import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  Pose,
  ProductSnapshot,
  RadiationClaim,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  TimeModel,
  VISUAL_SECTIONED_TUBE_V1 as CANONICAL_VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
)

_SECTIONED_TUBE_SCHEMA_VERSION = '1.0.0'


@dataclass(frozen=True)
class PrescribedSectionedTubeProvider:
  """Compatibility shell backed by the canonical prescribed visual provider."""

  payload: SectionedTubePayload
  frame: FrameRef
  provenance: Provenance
  applicability: Applicability = field(default_factory=lambda: Applicability(supported=True))
  fidelity: FidelityClaim = field(
      default_factory=lambda: FidelityClaim(
          model_fidelity=ModelFidelity.PRESCRIBED,
          validation_level=ValidationLevel.VERIFIED,
          claim_notes=('Prescribed geometry fixture; no spectral capability is implied.',),
      )
  )
  provider_id: UUID | None = None

  def __post_init__(self) -> None:
    payload_sha = calculate_content_sha256(self.payload)
    resolved_provider_id = self.provider_id
    if resolved_provider_id is None:
      identity = f'{self.provenance.model_id}:{self.provenance.model_version}:{payload_sha}'
      resolved_provider_id = uuid5(NAMESPACE_URL, identity)
    ####
    object.__setattr__(self, 'provider_id', resolved_provider_id)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    provider_id = self.provider_id
    if provider_id is None:
      raise RuntimeError('provider_id was not initialized')
    ####
    return ProviderDescriptor(
        provider_id=provider_id,
        provider_type='PrescribedSectionedTubeProvider',
        provider_version=self.provenance.model_version,
        capabilities=(
            CapabilityAdvertisement(
                capability_id=VISUAL_SECTIONED_TUBE_V1,
                schema_version=_SECTIONED_TUBE_SCHEMA_VERSION,
            ),
        ),
        static_time=True,
    )
  ####

  def create_session(self) -> PrescribedSectionedTubeSession:
    return PrescribedSectionedTubeSession(provider=self)
  ####

  def _canonical_definition(self) -> PrescribedVisualDefinition:
    """Translate the shipped alpha payload into the canonical geometry DTO."""

    return PrescribedVisualDefinition(
      frame_id=self.frame.frame_id,
      sections=tuple(
        VisualSection(
          arc_length_m=section.arc_length_m,
          center_m=section.center_m,
          section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
          radius_major_m=section.semi_axis_1_m,
          radius_minor_m=section.semi_axis_2_m,
        )
        for section in self.payload.sections
      ),
    )
  ####

  def _canonical_provider(self) -> PrescribedVisualProvider:
    provider_id = self.provider_id
    if provider_id is None:
      raise RuntimeError('provider_id was not initialized')
    ####
    return PrescribedVisualProvider(PrescribedVisualConfiguration(
      provider_id=str(provider_id),
      provider_version=self.provenance.model_version,
      geometry_claim=GeometryClaim.ILLUSTRATIVE,
      radiation_claim=RadiationClaim.APPEARANCE_ONLY,
      time_model=TimeModel.STEADY,
      derivation=Derivation.ADAPTED,
      consistency=ConsistencyLevel.INDEPENDENT,
      applicability_status=(
        ApplicabilityStatus.INSIDE if self.applicability.supported else ApplicabilityStatus.OUTSIDE
      ),
      applicability_reasons=self.applicability.violations,
    ))
  ####
####


class PrescribedSectionedTubeSession:
  """Sequential session creating immutable snapshots for a static provider."""

  def __init__(self, provider: PrescribedSectionedTubeProvider) -> None:
    self._provider = provider
    self._session_id = uuid4()
    self._closed = False
    self._canonical_session = provider._canonical_provider().create_session(
      definition=provider._canonical_definition(),
    )
  ####

  @property
  def session_id(self) -> UUID:
    return self._session_id
  ####

  def snapshot(self, request: SnapshotRequest) -> PrescribedSectionedTubeSnapshot:
    if self._closed:
      raise PlumeApiError(
          PlumeErrorCode.INVALID_REQUEST,
          'The plume session is closed.',
          provider_id=self._provider.descriptor.provider_id,
          session_id=self._session_id,
      )
    ####
    return PrescribedSectionedTubeSnapshot(
        provider=self._provider,
        session_id=self._session_id,
        request=request,
        canonical_snapshot=self._canonical_session.create_snapshot(
          time_s=request.time_s,
          source_pose=Pose(
            frame_id=self._provider.frame.frame_id,
            translation_m=self._provider.frame.pose_parent_from_frame.translation_m,
            rotation_xyzw=self._provider.frame.pose_parent_from_frame.rotation_xyzw,
          ),
          dynamic_state={},
          ambient_state={},
        ),
    )
  ####

  def close(self) -> None:
    self._closed = True
    self._canonical_session.close()
  ####
####


@dataclass(frozen=True)
class PrescribedSectionedTubeSnapshot:
  """Immutable snapshot exposing only the sectioned-tube visual capability."""

  provider: PrescribedSectionedTubeProvider
  session_id: UUID
  request: SnapshotRequest
  canonical_snapshot: ProductSnapshot = field(repr=False)
  snapshot_id: UUID = field(init=False)
  _result: SectionedTubeResult = field(init=False, repr=False)

  def __post_init__(self) -> None:
    object.__setattr__(self, 'snapshot_id', uuid4())
    result = SectionedTubeResult(
        envelope=ResultEnvelope(
            capability_id=VISUAL_SECTIONED_TUBE_V1,
            schema_version=_SECTIONED_TUBE_SCHEMA_VERSION,
            provider_id=self.provider.descriptor.provider_id,
            session_id=self.session_id,
            snapshot_id=self.snapshot_id,
            content_sha256=calculate_content_sha256(self.provider.payload),
            requested_time_s=self.request.time_s,
            actual_time_s=self.request.time_s,
            frame=self.provider.frame,
            status=ResultStatus.OK,
            fidelity=self.provider.fidelity,
            applicability=self.provider.applicability,
            provenance=self.provider.provenance,
        ),
        payload=self.provider.payload,
    )
    object.__setattr__(self, '_result', result)
  ####

  @property
  def requested_time_s(self) -> float:
    return self.request.time_s
  ####

  @property
  def actual_time_s(self) -> float:
    return self.request.time_s
  ####

  def get_product(self, request: ProductRequest) -> ProductResult:
    if request.capability_id != VISUAL_SECTIONED_TUBE_V1:
      raise PlumeApiError(
          PlumeErrorCode.CAPABILITY_NOT_SUPPORTED,
          f'Capability {request.capability_id!r} is not advertised by this provider.',
          details={'advertised_capabilities': [VISUAL_SECTIONED_TUBE_V1]},
          provider_id=self.provider.descriptor.provider_id,
          session_id=self.session_id,
          snapshot_id=self.snapshot_id,
      )
    ####
    if request.schema_version != _SECTIONED_TUBE_SCHEMA_VERSION:
      raise PlumeApiError(
          PlumeErrorCode.SCHEMA_VERSION_NOT_SUPPORTED,
          f'Schema {request.schema_version!r} is not supported for {VISUAL_SECTIONED_TUBE_V1}.',
          details={'supported_schema_versions': [_SECTIONED_TUBE_SCHEMA_VERSION]},
          provider_id=self.provider.descriptor.provider_id,
          session_id=self.session_id,
          snapshot_id=self.snapshot_id,
      )
    ####
    self.canonical_snapshot.evaluate(
      CANONICAL_VISUAL_SECTIONED_TUBE_V1,
      VisualSectionedTubeRequest(
        output_frame_id=self.provider.frame.frame_id,
        sampling=VisualSampling(maximum_section_count=len(self.provider.payload.sections)),
      ),
    )
    return self._result
  ####
####
