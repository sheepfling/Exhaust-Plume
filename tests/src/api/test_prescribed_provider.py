from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from exhaust_plume.api import (
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    VISUAL_SECTIONED_TUBE_V1,
    Applicability,
    FeatureAssociation,
    FeatureChannel,
    FrameRef,
    PlumeApiError,
    PlumeErrorCode,
    Pose3,
    PrescribedSectionedTubeProvider,
    ProductRequest,
    Provenance,
    SectionedTubePayload,
    SectionedTubeResult,
    SnapshotRequest,
    SupportDefinition,
    TubeSection,
    v1,
)


def _provider() -> PrescribedSectionedTubeProvider:
  sections = (
      TubeSection(
          arc_length_m=0.,
          center_m=(0., 0., 0.),
          tangent=(1., 0., 0.),
          normal_1=(0., 1., 0.),
          normal_2=(0., 0., 1.),
          semi_axis_1_m=.2,
          semi_axis_2_m=.2,
      ),
      TubeSection(
          arc_length_m=1.,
          center_m=(1., .1, -.2),
          tangent=(1., 0., 0.),
          normal_1=(0., 1., 0.),
          normal_2=(0., 0., 1.),
          semi_axis_1_m=.3,
          semi_axis_2_m=.3,
      ),
  )
  payload = SectionedTubePayload(
      sections=sections,
      feature_channels=(
          FeatureChannel(
              channel_id='temperature',
              semantic='temperature',
              unit='K',
              association=FeatureAssociation.SECTION,
              component_count=1,
              values=(620., 500.),
          ),
          FeatureChannel(
              channel_id='exhaust-mass-fraction',
              semantic='exhaust_mass_fraction',
              unit='1',
              association=FeatureAssociation.SECTION,
              component_count=1,
              values=(1., .5),
          ),
      ),
      support_definition=SupportDefinition(
          kind='ENCLOSED_EXHAUST_MASS_FRACTION',
          fraction=.95,
      ),
  )
  frame = FrameRef(
      frame_id='aircraft-body',
      parent_frame_id=None,
      pose_parent_from_frame=Pose3(
          translation_m=(0., 0., 0.),
          rotation_xyzw=(0., 0., 0., 1.),
      ),
  )
  provenance = Provenance(
      model_id='prescribed-washed-plume-fixture',
      model_version='1.0.0',
      code_revision='test',
      configuration_sha256='2' * 64,
  )
  return PrescribedSectionedTubeProvider(
      payload=payload,
      frame=frame,
      provenance=provenance,
      applicability=Applicability(supported=True, domain={'time': 'static'}),
  )
####


def test_provider_advertises_only_visual_product() -> None:
  provider = _provider()
  assert [capability.capability_id for capability in provider.descriptor.capabilities] == [VISUAL_SECTIONED_TUBE_V1]
####


def test_static_provider_uses_common_lifecycle_and_stable_content_hash() -> None:
  provider = _provider()
  session = provider.create_session()
  snapshot_a = session.snapshot(SnapshotRequest(time_s=2.))
  snapshot_b = session.snapshot(SnapshotRequest(time_s=9.))
  request = ProductRequest(capability_id=VISUAL_SECTIONED_TUBE_V1, schema_version='1.0.0')
  result_a = snapshot_a.get_product(request)
  result_b = snapshot_b.get_product(request)
  assert isinstance(result_a, SectionedTubeResult)
  assert result_a.envelope.requested_time_s == 2.
  assert result_a.envelope.actual_time_s == 2.
  assert result_b.envelope.actual_time_s == 9.
  assert result_a.envelope.content_sha256 == result_b.envelope.content_sha256
  assert result_a.payload == result_b.payload
####


def test_snapshot_supports_concurrent_immutable_reads() -> None:
  session = _provider().create_session()
  snapshot = session.snapshot(SnapshotRequest(time_s=1.))
  request = ProductRequest(capability_id=VISUAL_SECTIONED_TUBE_V1, schema_version='1.0.0')
  with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda _: snapshot.get_product(request), range(32)))
  ####
  assert all(result is results[0] for result in results)
####


def test_provider_rejects_unsupported_upward_inference() -> None:
  session = _provider().create_session()
  snapshot = session.snapshot(SnapshotRequest(time_s=0.))
  with pytest.raises(PlumeApiError) as exc_info:
    snapshot.get_product(
        ProductRequest(
            capability_id=SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
            schema_version='1.0.0',
        )
    )
  ####
  assert exc_info.value.code is PlumeErrorCode.CAPABILITY_NOT_SUPPORTED
####


def test_closed_session_rejects_new_snapshots() -> None:
  session = _provider().create_session()
  session.close()
  with pytest.raises(PlumeApiError) as exc_info:
    session.snapshot(SnapshotRequest(time_s=0.))
  ####
  assert exc_info.value.code is PlumeErrorCode.INVALID_REQUEST
####


def test_golden_washed_fixture_round_trips_and_matches_provider_payload() -> None:
  fixture_path = Path(__file__).parents[2] / 'fixtures' / 'sectioned_tube_washed_v1.json'
  fixture = SectionedTubeResult.model_validate_json(fixture_path.read_text(encoding='utf-8'))
  provider = PrescribedSectionedTubeProvider(
      payload=fixture.payload,
      frame=fixture.envelope.frame,
      provenance=fixture.envelope.provenance,
      applicability=fixture.envelope.applicability,
      fidelity=fixture.envelope.fidelity,
      provider_id=fixture.envelope.provider_id,
  )
  session = provider.create_session()
  snapshot = session.snapshot(SnapshotRequest(time_s=42.))
  product = snapshot.get_product(
      ProductRequest(capability_id=VISUAL_SECTIONED_TUBE_V1, schema_version='1.0.0')
  )
  assert product.payload == fixture.payload
  assert product.envelope.content_sha256 == fixture.envelope.content_sha256


def test_legacy_prescribed_shell_delegates_to_canonical_snapshot() -> None:
  snapshot = _provider().create_session().snapshot(SnapshotRequest(time_s=3.0))
  assert isinstance(snapshot.canonical_snapshot, v1.ProductSnapshot)
  canonical_result = snapshot.canonical_snapshot.evaluate(
    v1.VISUAL_SECTIONED_TUBE_V1,
    v1.VisualSectionedTubeRequest(
      output_frame_id='aircraft-body',
      sampling=v1.VisualSampling(maximum_section_count=2),
    ),
  )
  assert canonical_result.metadata.capability == v1.VISUAL_SECTIONED_TUBE_CAPABILITY
  assert canonical_result.metadata.snapshot.time_s == 3.0
####
