from __future__ import annotations

from collections.abc import Callable

import pytest

from exhaust_plume.products import (
    Aabb3,
    CapabilityId,
    ProductMetadata,
    SectionedTubeProduct,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.providers import (
    ClosedSessionError,
    ExecutionBackend,
    ProviderDescriptor,
    StaticPlumeProvider,
    TimeAccessMode,
    UnsupportedCapabilityError,
    requireProduct,
)


def _visualProduct(metadata: ProductMetadata) -> SectionedTubeProduct:
  return SectionedTubeProduct(
      metadata=metadata,
      centerline_m=((0., 0., 0.), (1., 0., 0.)),
      tangents_unit=((1., 0., 0.), (1., 0., 0.)),
      normals_unit=((0., 1., 0.), (0., 1., 0.)),
      binormals_unit=((0., 0., 1.), (0., 0., 1.)),
      semi_major_axis_m=(.1, .1),
      semi_minor_axis_m=(.1, .1),
      bounds=Aabb3(minimum_m=(0., -.1, -.1), maximum_m=(1., .1, .1)),
  )
####


def testStaticVisualProviderAdvertisesOnlySuppliedProduct(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  metadata = metadata_factory(VISUAL_SECTIONED_TUBE_V1)
  visual = _visualProduct(metadata)
  descriptor = ProviderDescriptor(
      provider_id='visual-fixture',
      provider_version='0.1.0',
      display_name='Visual Fixture',
      capabilities=(VISUAL_SECTIONED_TUBE_V1,),
      time_access_mode=TimeAccessMode.STATIC,
      supported_backends=(ExecutionBackend.CPU,),
      provenance=metadata.provenance,
  )
  provider = StaticPlumeProvider(
      descriptor=descriptor,
      product_by_capability={VISUAL_SECTIONED_TUBE_V1: visual},
      snapshot_id='snapshot-1',
      time_s=0.,
  )
  with provider.createSession() as session:
    snapshot = session.snapshot(0.)
    assert requireProduct(snapshot, VISUAL_SECTIONED_TUBE_V1, SectionedTubeProduct) == visual
    with pytest.raises(UnsupportedCapabilityError):
      snapshot.getProduct(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1)
    ####
  ####
  assert session.is_closed
  with pytest.raises(ClosedSessionError):
    session.snapshot(0.)
  ####
####


def testStaticProviderRejectsProductCapabilityMismatch(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  metadata = metadata_factory(VISUAL_SECTIONED_TUBE_V1)
  descriptor = ProviderDescriptor(
      provider_id='invalid-fixture',
      provider_version='0.1.0',
      display_name='Invalid Fixture',
      capabilities=(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,),
      time_access_mode=TimeAccessMode.STATIC,
      provenance=metadata.provenance,
  )
  with pytest.raises(ValueError):
    StaticPlumeProvider(
        descriptor=descriptor,
        product_by_capability={SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1: _visualProduct(metadata)},
        snapshot_id='snapshot-1',
        time_s=0.,
    )
  ####
####
