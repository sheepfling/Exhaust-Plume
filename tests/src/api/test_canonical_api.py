from __future__ import annotations

import importlib
from pathlib import Path
from uuid import uuid4

import pytest

import exhaust_plume
from exhaust_plume import api, contracts
from exhaust_plume.api import (
  PlumeApiError,
  PlumeErrorCode,
  ProductRequest,
  SnapshotRequest,
  v1,
)
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / 'fixtures' / 'contracts'


@pytest.mark.parametrize(
  ('module_name',),
  (
    ('exhaust_plume.api',),
    ('exhaust_plume.api.v1',),
    ('exhaust_plume.contracts',),
    ('exhaust_plume.products',),
    ('exhaust_plume.providers',),
    ('exhaust_plume',),
  ),
)
def test_public_import_inventory_resolves(module_name: str) -> None:
  module = importlib.import_module(module_name)
  public_names = getattr(module, '__all__')
  assert public_names
  assert len(public_names) == len(set(public_names))
  assert all(hasattr(module, name) for name in public_names)
####


def test_v1_facade_is_aliases_not_a_second_wire_model_tree() -> None:
  assert v1.VisualSectionedTubeRequest is contracts.VisualSectionedTubeRequest
  assert v1.VisualSectionedTubeResult is contracts.VisualSectionedTubeResult
  assert v1.SpectralSignatureRequest is contracts.SpectralSignatureRequest
  assert v1.SpectralSignatureResult is contracts.SpectralSignatureResult
  assert v1.SpectralRayTransferRequest is contracts.SpectralRayTransferRequest
  assert v1.SpectralRayTransferResult is contracts.VersionedSpectralRayTransferResult
  assert v1.ProviderDescriptor is contracts.ProviderDescriptor
  assert v1.ResultMetadata is contracts.ResultMetadata
  assert v1.PUBLIC_CONTRACT_MODELS is contracts.PUBLIC_CONTRACT_MODELS
  assert v1.export_public_schemas is contracts.export_public_schemas
  assert v1.VISUAL_SECTIONED_TUBE_V1 is contracts.VISUAL_SECTIONED_TUBE_V1
  assert v1.SPECTRAL_RADIANT_INTENSITY_V1 is contracts.SPECTRAL_RADIANT_INTENSITY_V1
  assert v1.SPECTRAL_RAY_TRANSFER_V1 is contracts.SPECTRAL_RAY_TRANSFER_V1
####


def test_canonical_registry_owns_primary_and_supporting_identities() -> None:
  assert len(v1.CANONICAL_CAPABILITY_REGISTRY) == 9
  assert tuple(v1.CANONICAL_CAPABILITY_REGISTRY) == tuple(
    capability.wire_id for capability in v1.CANONICAL_CAPABILITY_IDENTITIES
  )
  assert tuple(v1.PRIMARY_CAPABILITY_IDENTITIES) == tuple(
    v1.CANONICAL_CAPABILITY_REGISTRY[capability.wire_id]
    for capability in v1.PRIMARY_CAPABILITY_IDENTITIES
  )
  assert v1.get_product_capability_spec('plume.visual.sectioned-tube@1') is v1.VISUAL_SECTIONED_TUBE_V1
  with pytest.raises(v1.UnsupportedProductVersionError):
    v1.get_product_capability_spec('plume.visual.sectioned-tube@2')
  ####
  with pytest.raises(v1.UnsupportedProductCapabilityError):
    v1.get_product_capability_spec('plume.product.unknown@1')
  ####
####


@pytest.mark.parametrize(
  ('fixture_name', 'canonical_model', 'wire_model'),
  (
    (
      'visual_sectioned_tube_v1.json',
      v1.VisualSectionedTubeResult,
      contracts.VisualSectionedTubeResult,
    ),
    (
      'spectral_signature_v1.json',
      v1.SpectralSignatureResult,
      contracts.SpectralSignatureResult,
    ),
    (
      'spectral_ray_transfer_v1.json',
      v1.SpectralRayTransferResult,
      contracts.VersionedSpectralRayTransferResult,
    ),
  ),
)
def test_v1_facade_round_trips_checked_in_golden_fixtures(
    fixture_name: str,
    canonical_model: type,
    wire_model: type,
) -> None:
  serialized = (FIXTURE_ROOT / fixture_name).read_text(encoding='utf-8')
  canonical = canonical_model.model_validate_json(serialized)
  wire = wire_model.model_validate_json(serialized)
  assert canonical.model_dump(mode='json') == wire.model_dump(mode='json')
  assert v1.canonical_digest(canonical.model_dump(mode='json')) == v1.canonical_digest(
    wire.model_dump(mode='json')
  )
####


def test_v1_facade_preserves_structured_rejection_for_invalid_fixture() -> None:
  with pytest.raises(ValueError, match='strictly increasing'):
    v1.VisualSectionedTubeResult.model_validate_json(
      (FIXTURE_ROOT / 'invalid_visual_nonmonotonic.json').read_text(encoding='utf-8')
    )
  ####
####


def test_existing_visual_consumer_runs_through_canonical_namespace() -> None:
  definition = PrescribedVisualDefinition(
    frame_id='world',
    sections=(
      v1.VisualSection(
        arc_length_m=0.0,
        center_m=(0.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.25,
        radius_minor_m=0.20,
      ),
      v1.VisualSection(
        arc_length_m=1.0,
        center_m=(1.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.30,
        radius_minor_m=0.24,
      ),
    ),
  )
  snapshot = PrescribedVisualProvider().create_session(
    definition=definition,
  ).create_snapshot(
    time_s=0.0,
    source_pose=v1.Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(
    v1.VISUAL_SECTIONED_TUBE_V1,
    v1.VisualSectionedTubeRequest(
      output_frame_id='world',
      sampling=v1.VisualSampling(maximum_section_count=2),
    ),
  )
  assert isinstance(result, v1.VisualSectionedTubeResult)
  assert result.metadata.capability == v1.VISUAL_SECTIONED_TUBE_CAPABILITY
  assert result.sections[-1].arc_length_m == 1.0
####


def test_lifecycle_adapters_round_trip_canonical_result_and_request() -> None:
  definition = PrescribedVisualDefinition(
    frame_id='world',
    sections=(
      v1.VisualSection(
        arc_length_m=0.0,
        center_m=(0.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.25,
        radius_minor_m=0.20,
      ),
      v1.VisualSection(
        arc_length_m=1.0,
        center_m=(1.0, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=0.30,
        radius_minor_m=0.24,
      ),
    ),
  )
  source_pose = v1.Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  typed_request = v1.VisualSectionedTubeRequest(
    output_frame_id='world',
    sampling=v1.VisualSampling(maximum_section_count=2),
  )
  canonical_session = PrescribedVisualProvider().create_session(definition=definition)
  legacy_session = v1.CanonicalSessionLegacyAdapter(
    session=canonical_session,
    source_pose=source_pose,
    dynamic_state={},
    ambient_state={},
    bound_requests={
      v1.VISUAL_SECTIONED_TUBE_CAPABILITY.wire_id: (
        v1.VISUAL_SECTIONED_TUBE_V1,
        typed_request,
      ),
    },
  )
  legacy_request = v1.legacy_request_from_capability(v1.VISUAL_SECTIONED_TUBE_V1)
  assert isinstance(legacy_request, ProductRequest)
  assert v1.canonical_capability_from_legacy_request(legacy_request) == v1.VISUAL_SECTIONED_TUBE_CAPABILITY
  legacy_snapshot = legacy_session.snapshot(SnapshotRequest(time_s=0.0))
  result = legacy_snapshot.get_product(legacy_request)
  assert isinstance(result, v1.VisualSectionedTubeResult)

  class _LegacySnapshot:
    def get_product(self, request: ProductRequest) -> object:
      assert request == legacy_request
      return result
    ####
  ####

  canonical_snapshot = v1.LegacySnapshotCanonicalAdapter(
    snapshot=_LegacySnapshot(),
    supported_capabilities=(v1.VISUAL_SECTIONED_TUBE_CAPABILITY,),
    result_adapters={v1.VISUAL_SECTIONED_TUBE_CAPABILITY.wire_id: lambda value: value},
  )
  round_tripped = canonical_snapshot.evaluate(v1.VISUAL_SECTIONED_TUBE_V1, typed_request)
  assert round_tripped is result
####


def test_error_adapters_preserve_structured_context_and_equivalent_code() -> None:
  provider_id = uuid4()
  session_id = uuid4()
  snapshot_id = uuid4()
  legacy = PlumeApiError(
    PlumeErrorCode.CAPABILITY_NOT_SUPPORTED,
    'visual capability is unavailable',
    details={'requested': 'plume.visual.sectioned-tube@1'},
    provider_id=provider_id,
    session_id=session_id,
    snapshot_id=snapshot_id,
  )
  canonical = v1.canonical_error_from_legacy(legacy)
  assert canonical.code is v1.ErrorCode.UNSUPPORTED_CAPABILITY
  assert canonical.provider_id == str(provider_id)
  assert canonical.snapshot_id == str(snapshot_id)
  assert canonical.details['session_id'] == str(session_id)
  restored = v1.legacy_error_from_canonical(canonical)
  assert restored.code is PlumeErrorCode.CAPABILITY_NOT_SUPPORTED
  assert restored.provider_id == provider_id
  assert restored.session_id == session_id
  assert restored.snapshot_id == snapshot_id
####


def test_root_contract_imports_remain_compatible() -> None:
  assert exhaust_plume.VisualSectionedTubeResult is v1.VisualSectionedTubeResult
  assert exhaust_plume.SpectralSignatureResult is v1.SpectralSignatureResult
  assert exhaust_plume.VersionedSpectralRayTransferResult is v1.VersionedSpectralRayTransferResult
  assert api.v1 is v1
####
