from __future__ import annotations

from collections.abc import Callable

import pytest

from exhaust_plume.products import (
    Aabb3,
    CapabilityId,
    ProductMetadata,
    Provenance,
    SectionedTubeProduct,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers import (
    ClosedSessionError,
    ExecutionBackend,
    ProviderDescriptor,
    SessionRequest,
    StaticPlumeProvider,
    StaticVisualCapability,
    TimeAccessMode,
    UnsupportedCapabilityError,
    VisualSectionedTubeCapability,
    requireCapability,
)

MetadataFactory = Callable[[CapabilityId, str, str, float], ProductMetadata]


def makeVisual(
    metadata_factory: MetadataFactory,
    *,
    snapshot_id: str = 'snapshot-1',
    time_s: float = 0.,
) -> SectionedTubeProduct:
  return SectionedTubeProduct(
      metadata=metadata_factory(
          VISUAL_SECTIONED_TUBE_V1,
          'visual-1',
          snapshot_id,
          time_s,
      ),
      centerline_m=((0., 0., 0.), (1., 0., 0.)),
      tangents_unit=((1., 0., 0.), (1., 0., 0.)),
      normals_unit=((0., 1., 0.), (0., 1., 0.)),
      binormals_unit=((0., 0., 1.), (0., 0., 1.)),
      semi_major_axis_m=(1., 1.),
      semi_minor_axis_m=(1., 1.),
      bounds=Aabb3(minimum_m=(0., -1., -1.), maximum_m=(1., 1., 1.)),
  )
####


def makeDescriptor() -> ProviderDescriptor:
  return ProviderDescriptor(
      provider_id='fixture.visual',
      provider_version='0.1.0',
      display_name='Fixture visual provider',
      capabilities=(VISUAL_SECTIONED_TUBE_V1,),
      time_access_mode=TimeAccessMode.STATIC,
      supported_backends=(ExecutionBackend.CPU,),
      provenance=Provenance(
          provider_id='fixture.visual',
          provider_version='0.1.0',
          model_name='prescribed-fixture',
          model_revision='1',
      ),
  )
####


def makeProvider(metadata_factory: MetadataFactory) -> StaticPlumeProvider:
  return StaticPlumeProvider(
      descriptor=makeDescriptor(),
      binding_by_capability={
          VISUAL_SECTIONED_TUBE_V1: StaticVisualCapability(makeVisual(metadata_factory)),
      },
      snapshot_id='snapshot-1',
      time_s=0.,
  )
####


def testStaticProviderAdvertisesOnlySuppliedCapability(metadata_factory: MetadataFactory) -> None:
  provider = makeProvider(metadata_factory)
  assert provider.descriptor.capabilities == (VISUAL_SECTIONED_TUBE_V1,)
  with provider.createSession() as session:
    snapshot = session.snapshot(0.)
    capability = requireCapability(
        snapshot,
        VISUAL_SECTIONED_TUBE_V1,
        VisualSectionedTubeCapability,
    )
    assert capability.getSectionedTube().metadata.product_id == 'visual-1'
  ####
  assert session.is_closed
####


def testUnsupportedCapabilityFailsStructurally(metadata_factory: MetadataFactory) -> None:
  provider = makeProvider(metadata_factory)
  snapshot = provider.createSession().snapshot(0.)
  unknown = CapabilityId(name='plume.signature.synthetic', major=1)
  with pytest.raises(UnsupportedCapabilityError) as error:
    snapshot.resolveCapability(unknown)
  ####
  assert error.value.provider_id == 'fixture.visual'
  assert error.value.capability == unknown
####


def testStaticSessionRejectsOtherTimeAndUseAfterClose(metadata_factory: MetadataFactory) -> None:
  session = makeProvider(metadata_factory).createSession(
      SessionRequest(backend=ExecutionBackend.CPU)
  )
  with pytest.raises(ValueError, match='only supports time'):
    session.snapshot(1.)
  ####
  session.close()
  with pytest.raises(ClosedSessionError):
    session.snapshot(0.)
  ####
####


def testProviderRejectsMissingStaticBindings() -> None:
  with pytest.raises(ValueError, match='at least one static capability binding'):
    StaticPlumeProvider(
        descriptor=makeDescriptor(),
        binding_by_capability={},
        snapshot_id='snapshot-1',
        time_s=0.,
    )
  ####
####


def testStaticProductMetadataMustMatchOwningSnapshot(metadata_factory: MetadataFactory) -> None:
  product = makeVisual(metadata_factory, snapshot_id='other-snapshot')
  with pytest.raises(ValueError, match='owning snapshot'):
    StaticPlumeProvider(
        descriptor=makeDescriptor(),
        binding_by_capability={
            VISUAL_SECTIONED_TUBE_V1: StaticVisualCapability(product),
        },
        snapshot_id='snapshot-1',
        time_s=0.,
    )
  ####
####
