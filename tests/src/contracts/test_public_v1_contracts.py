from __future__ import annotations

import pytest

from exhaust_plume.contracts import (
  ApplicabilityReport,
  ApplicabilityStatus,
  CapabilityIdentity,
  CapabilitySpec,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  InvalidProductRequestError,
  LodProfile,
  Pose,
  ProductClaims,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SessionMetadata,
  SnapshotMetadata,
  SpectralSignatureRequest,
  SpectralSignatureResult,
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  SPECTRAL_RAY_TRANSFER_V1,
  SpectralRayTransferRequest,
  VersionedSpectralRayTransferResult,
  TimeModel,
  UnsupportedProductCapabilityError,
  UnsupportedProductVersionError,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualBounds,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  VisualTubeSummary,
  canonical_digest,
)


def _snapshot_metadata() -> SnapshotMetadata:
  return SnapshotMetadata(
    snapshot_id='snapshot-1',
    session_id='session-1',
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state_digest_sha256='dynamic',
    ambient_state_digest_sha256='ambient',
    provider_state_digest_sha256='provider',
  )
####


def _result_metadata(capability: CapabilityIdentity) -> ResultMetadata:
  return ResultMetadata(
    capability=capability,
    result_id='result-1',
    request_digest_sha256='request',
    snapshot=_snapshot_metadata(),
    output_frame_id='world',
    claims=ProductClaims(
      geometry=GeometryClaim.ILLUSTRATIVE,
      radiation=RadiationClaim.APPEARANCE_ONLY,
      time_model=TimeModel.STEADY,
      derivation=Derivation.NATIVE,
      consistency=ConsistencyLevel.INDEPENDENT,
    ),
    applicability=ApplicabilityReport(status=ApplicabilityStatus.INSIDE),
    provenance=ResultProvenance(
      model_lineage_id='lineage-1',
      provider_id='provider.fixture',
      provider_version='1.0.0',
      configuration_digest_sha256='configuration',
    ),
  )
####


def _visual_result() -> VisualSectionedTubeResult:
  return VisualSectionedTubeResult(
    metadata=_result_metadata(VISUAL_SECTIONED_TUBE_CAPABILITY),
    sections=(
      VisualSection(
        arc_length_m=0.0,
        center_m=(0.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.5,
        radius_minor_m=0.25,
      ),
      VisualSection(
        arc_length_m=1.0,
        center_m=(1.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.6,
        radius_minor_m=0.3,
      ),
    ),
    channels={'mixing_weight': (0.0, 1.0)},
    visual_bounds=VisualBounds(
      minimum_m=(-0.6, -0.6, -0.6),
      maximum_m=(1.6, 0.6, 0.6),
    ),
    summary=VisualTubeSummary(length_m=1.0, maximum_radius_m=0.6),
  )
####


def test_capability_identity_is_parseable_and_digest_is_stable() -> None:
  capability = CapabilityIdentity.parse('plume.visual.sectioned-tube@1')
  assert capability == VISUAL_SECTIONED_TUBE_CAPABILITY
  assert capability.wire_id == 'plume.visual.sectioned-tube@1'
  assert canonical_digest({'b': 2, 'a': 1}) == canonical_digest({'a': 1, 'b': 2})
####


def test_visual_contract_validates_geometry_and_channels() -> None:
  request = VisualSectionedTubeRequest(
    output_frame_id='world',
    sampling=VisualSampling(maximum_section_count=32, lod_profile=LodProfile.STANDARD),
    requested_channels=('mixing_weight',),
  )
  assert request.sampling.maximum_section_count == 32
  result = _visual_result()
  assert len(result.sections) == len(result.channels['mixing_weight'])
  with pytest.raises(ValueError, match='strictly increasing'):
    VisualSectionedTubeResult(
      metadata=result.metadata,
      sections=(result.sections[0], result.sections[0]),
      summary=result.summary,
    )
  ####
  with pytest.raises(ValueError, match='normalized channel'):
    VisualSectionedTubeResult(
      metadata=result.metadata,
      sections=result.sections,
      channels={'mixing_weight': (0.0, 2.0)},
      summary=result.summary,
    )
  ####
####


def test_signature_contract_requires_neutral_placeholders_for_failed_rows() -> None:
  request = SpectralSignatureRequest(
    direction_frame_id='source',
    source_to_observer_directions=((1.0, 0.0, 0.0),),
    wavelengths_m=(2.0e-6, 4.0e-6),
  )
  assert request.wavelengths_m == (2.0e-6, 4.0e-6)
  result = SpectralSignatureResult(
    metadata=_result_metadata(SPECTRAL_RADIANT_INTENSITY_CAPABILITY),
    spectral_radiant_intensity=((0.0, 0.0),),
    validity_mask=((False, False),),
    direction_status=(SampleStatus(code=SampleStatusCode.OUTSIDE_APPLICABILITY),),
  )
  assert result.direction_status[0].code is SampleStatusCode.OUTSIDE_APPLICABILITY
  with pytest.raises(ValueError, match='zero placeholder'):
    SpectralSignatureResult(
      metadata=result.metadata,
      spectral_radiant_intensity=((1.0, 0.0),),
      validity_mask=((False, False),),
      direction_status=(SampleStatus(code=SampleStatusCode.OUTSIDE_APPLICABILITY),),
    )
  ####
####


def test_ray_contract_distinguishes_valid_miss_from_failed_sample() -> None:
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((0.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(2.0e-6,),
  )
  assert request.ray_t_max_m == (10.0,)
  miss = VersionedSpectralRayTransferResult(
    metadata=_result_metadata(SPECTRAL_RAY_TRANSFER_CAPABILITY),
    source_spectral_radiance=((0.0,),),
    background_transmittance=((1.0,),),
    validity_mask=((True,),),
    ray_status=(SampleStatus(code=SampleStatusCode.OK),),
    hit_mask=(False,),
  )
  assert miss.hit_mask == (False,)
  with pytest.raises(ValueError, match='miss ray'):
    VersionedSpectralRayTransferResult(
      metadata=miss.metadata,
      source_spectral_radiance=((1.0,),),
      background_transmittance=((1.0,),),
      validity_mask=((True,),),
      ray_status=(SampleStatus(code=SampleStatusCode.OK),),
      hit_mask=(False,),
    )
  ####
####


def test_immutable_snapshot_dispatches_by_capability_and_version() -> None:
  class _Evaluator:
    def evaluate(self, request: VisualSectionedTubeRequest, snapshot: SnapshotMetadata) -> VisualSectionedTubeResult:
      assert request.output_frame_id == snapshot.source_pose.frame_id
      return _visual_result()
    ####
  ####

  snapshot = ImmutableProductSnapshot(
    metadata=_snapshot_metadata(),
    _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _Evaluator()},
  )
  result = snapshot.evaluate(
    CapabilitySpec(
      capability=VISUAL_SECTIONED_TUBE_CAPABILITY,
      request_type=VisualSectionedTubeRequest,
      result_type=VisualSectionedTubeResult,
    ),
    VisualSectionedTubeRequest(
      output_frame_id='world',
      sampling=VisualSampling(maximum_section_count=2),
    ),
  )
  assert result.metadata.capability == VISUAL_SECTIONED_TUBE_CAPABILITY
  with pytest.raises(UnsupportedProductCapabilityError):
    snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((0.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(1.0,),
      wavelengths_m=(2.0e-6,),
    ))
  ####
  with pytest.raises(UnsupportedProductVersionError):
    snapshot.evaluate(
      CapabilitySpec(
        capability=CapabilityIdentity(name='plume.visual.sectioned-tube', major=2),
        request_type=VisualSectionedTubeRequest,
        result_type=VisualSectionedTubeResult,
      ),
      VisualSectionedTubeRequest(
        output_frame_id='world',
        sampling=VisualSampling(maximum_section_count=2),
      ),
    )
  ####
  with pytest.raises(InvalidProductRequestError):
    snapshot.evaluate(  # type: ignore[arg-type]
      CapabilitySpec(
        capability=VISUAL_SECTIONED_TUBE_CAPABILITY,
        request_type=VisualSectionedTubeRequest,
        result_type=VisualSectionedTubeResult,
      ),
      request='not-a-request',
    )
  ####
####


def test_session_metadata_is_a_distinct_lifecycle_object() -> None:
  metadata = SessionMetadata(
    session_id='session-1',
    provider_id='provider.fixture',
    provider_version='1.0.0',
    configuration_digest_sha256='configuration',
  )
  assert metadata.provider_id == 'provider.fixture'
####


def test_public_capability_constants_are_separate_products() -> None:
  assert VISUAL_SECTIONED_TUBE_CAPABILITY != SPECTRAL_RADIANT_INTENSITY_CAPABILITY
  assert SPECTRAL_RADIANT_INTENSITY_CAPABILITY != SPECTRAL_RAY_TRANSFER_CAPABILITY
  assert SPECTRAL_RAY_TRANSFER_V1.capability == SPECTRAL_RAY_TRANSFER_CAPABILITY
####
