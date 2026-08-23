from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from exhaust_plume.products import (
    Aabb3,
    BatchValidity,
    CapabilityId,
    CompletionStatus,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    ProductMetadata,
    RayDefinition,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    SectionedTubeProduct,
    SpectralAxis,
    SpectralCoordinateKind,
    SpectralRadiantIntensityProduct,
    SpectralRayTransferProduct,
    VISUAL_SECTIONED_TUBE_V1,
    VisualFeatureChannel,
)


def testCapabilityIdentityRoundTrip() -> None:
  capability = CapabilityId.parse('plume.visual.sectioned-tube@1')
  assert capability == VISUAL_SECTIONED_TUBE_V1
  assert str(capability) == 'plume.visual.sectioned-tube@1'
####


def testCapabilityIdentityRejectsMissingMajor() -> None:
  with pytest.raises(ValueError):
    CapabilityId.parse('plume.visual.sectioned-tube')
  ####
####


def testCapabilityIdentityRejectsCoercedBooleanMajor() -> None:
  with pytest.raises(ValidationError):
    CapabilityId(name='plume.visual.sectioned-tube', major=True)
  ####
####


def testSpectralAxisRejectsUnsortedCoordinates() -> None:
  with pytest.raises(ValidationError):
    SpectralAxis(
        kind=SpectralCoordinateKind.WAVELENGTH,
        values=(4.e-6, 3.e-6),
        coordinate_unit='m',
    )
  ####
####


def _visualProduct(metadata: ProductMetadata) -> SectionedTubeProduct:
  return SectionedTubeProduct(
      metadata=metadata,
      centerline_m=((0., 0., 0.), (1., 0., 0.)),
      tangents_unit=((1., 0., 0.), (1., 0., 0.)),
      normals_unit=((0., 1., 0.), (0., 1., 0.)),
      binormals_unit=((0., 0., 1.), (0., 0., 1.)),
      semi_major_axis_m=(.2, .3),
      semi_minor_axis_m=(.2, .3),
      bounds=Aabb3(minimum_m=(0., -.3, -.3), maximum_m=(1., .3, .3)),
      feature_channels=(
          VisualFeatureChannel(
              name='temperature',
              unit='K',
              meaning='Visual diagnostic only.',
              values=(1000., 900.),
          ),
      ),
  )
####


def testVisualProductIsFrozenAndValidatesFrame(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  product = _visualProduct(metadata_factory(VISUAL_SECTIONED_TUBE_V1))
  assert product.geometry_role == 'visualization'
  with pytest.raises(ValidationError):
    product.centerline_m = ((0., 0., 0.), (2., 0., 0.))  # type: ignore[misc]
  ####
####


def testVisualBoundsMustEncloseSections(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  metadata = metadata_factory(VISUAL_SECTIONED_TUBE_V1)
  with pytest.raises(ValidationError):
    SectionedTubeProduct(
        metadata=metadata,
        centerline_m=((0., 0., 0.), (1., 0., 0.)),
        tangents_unit=((1., 0., 0.), (1., 0., 0.)),
        normals_unit=((0., 1., 0.), (0., 1., 0.)),
        binormals_unit=((0., 0., 1.), (0., 0., 1.)),
        semi_major_axis_m=(.2, .3),
        semi_minor_axis_m=(.2, .3),
        bounds=Aabb3(minimum_m=(0., -.1, -.1), maximum_m=(1., .1, .1)),
    )
  ####
####


def testSignatureProductIsIntrinsic(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  product = SpectralRadiantIntensityProduct(
      metadata=metadata_factory(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
      spectral_axis=SpectralAxis(
          kind=SpectralCoordinateKind.WAVELENGTH,
          values=(3.e-6, 4.e-6),
          coordinate_unit='m',
      ),
      directions_unit=((1., 0., 0.), (0., 1., 0.)),
      radiant_intensity=((1., 2.), (3., 4.)),
      value_unit='W sr^-1 m^-1',
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True, True)),
  )
  assert product.includes_range_loss is False
  assert product.includes_external_atmosphere is False
  assert product.radiant_intensity[1][1] == 4.
####


def testSignatureShapeMustMatchDirectionAndSpectrum(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  with pytest.raises(ValidationError):
    SpectralRadiantIntensityProduct(
        metadata=metadata_factory(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
        spectral_axis=SpectralAxis(
            kind=SpectralCoordinateKind.WAVELENGTH,
            values=(3.e-6, 4.e-6),
            coordinate_unit='m',
        ),
        directions_unit=((1., 0., 0.),),
        radiant_intensity=((1.,),),
        value_unit='W sr^-1 m^-1',
        validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
    )
  ####
####


def testRayTransferSeparatesSourceAndTransmittance(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  product = SpectralRayTransferProduct(
      metadata=metadata_factory(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
      spectral_axis=SpectralAxis(
          kind=SpectralCoordinateKind.WAVELENGTH,
          values=(3.e-6, 4.e-6),
          coordinate_unit='m',
      ),
      rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
      source_radiance=((5., 6.),),
      source_radiance_unit='W m^-2 sr^-1 m^-1',
      background_transmittance=((.8, .7),),
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
  )
  background = (10., 20.)
  composed = tuple(
      background[index] * product.background_transmittance[0][index]
      + product.source_radiance[0][index]
      for index in range(2)
  )
  assert composed == pytest.approx((13., 20.))
####


def testRayTransferRejectsInvalidTransmittance(
    metadata_factory: Callable[[CapabilityId, str], ProductMetadata],
) -> None:
  with pytest.raises(ValidationError):
    SpectralRayTransferProduct(
        metadata=metadata_factory(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
        spectral_axis=SpectralAxis(
            kind=SpectralCoordinateKind.WAVELENGTH,
            values=(3.e-6,),
            coordinate_unit='m',
        ),
        rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
        source_radiance=((5.,),),
        source_radiance_unit='W m^-2 sr^-1 m^-1',
        background_transmittance=((1.01,),),
        validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
    )
  ####
####


def testPartialBatchRequiresInvalidEntry() -> None:
  with pytest.raises(ValidationError):
    BatchValidity(status=CompletionStatus.PARTIAL, valid=(True, True))
  ####
####
