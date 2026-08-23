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

MetadataFactory = Callable[[CapabilityId, str, str, float], ProductMetadata]


def makeAxis() -> SpectralAxis:
  return SpectralAxis(
      kind=SpectralCoordinateKind.WAVELENGTH,
      values=(3.e-6, 4.e-6),
      coordinate_unit='m',
  )
####


def makeVisual(metadata_factory: MetadataFactory) -> SectionedTubeProduct:
  return SectionedTubeProduct(
      metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
      centerline_m=((0., 0., 0.), (1., 0., 0.)),
      tangents_unit=((1., 0., 0.), (1., 0., 0.)),
      normals_unit=((0., 1., 0.), (0., 1., 0.)),
      binormals_unit=((0., 0., 1.), (0., 0., 1.)),
      semi_major_axis_m=(1., 2.),
      semi_minor_axis_m=(1., 2.),
      bounds=Aabb3(minimum_m=(0., -2., -2.), maximum_m=(1., 2., 2.)),
      feature_channels=(
          VisualFeatureChannel(
              name='temperature',
              unit='K',
              meaning='Visual diagnostic only.',
              values=(900., 700.),
          ),
      ),
  )
####


def testCapabilityIdRoundTrips() -> None:
  capability = CapabilityId.parse('plume.visual.sectioned-tube@1')
  assert capability == VISUAL_SECTIONED_TUBE_V1
  assert str(capability) == 'plume.visual.sectioned-tube@1'
####


@pytest.mark.parametrize('value', ('missing-version', 'Bad.Name@1', 'plume.visual@0', '@1'))
def testCapabilityIdRejectsInvalidForms(value: str) -> None:
  with pytest.raises((ValueError, ValidationError)):
    CapabilityId.parse(value)
  ####
####


def testSpectralAxisRejectsWrongUnitAndNonmonotonicValues() -> None:
  with pytest.raises(ValidationError, match="coordinate unit 'm'"):
    SpectralAxis(
        kind=SpectralCoordinateKind.WAVELENGTH,
        values=(3.e-6, 4.e-6),
        coordinate_unit='1/m',
    )
  ####
  with pytest.raises(ValidationError, match='strictly increasing'):
    SpectralAxis(
        kind=SpectralCoordinateKind.WAVENUMBER,
        values=(250000., 240000.),
        coordinate_unit='1/m',
    )
  ####
####


def testSectionedTubeValidatesFrameBoundsAndChannels(
    metadata_factory: MetadataFactory,
) -> None:
  product = makeVisual(metadata_factory)
  assert product.geometry_role == 'visualization'
  assert product.feature_channels[0].name == 'temperature'
  assert product.model_dump_json() == product.model_dump_json()
####


def testSectionedTubeRejectsNonorthogonalFrame(metadata_factory: MetadataFactory) -> None:
  with pytest.raises(ValidationError, match='not orthogonal'):
    SectionedTubeProduct(
        metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
        centerline_m=((0., 0., 0.), (1., 0., 0.)),
        tangents_unit=((1., 0., 0.), (1., 0., 0.)),
        normals_unit=((1., 0., 0.), (1., 0., 0.)),
        binormals_unit=((0., 0., 1.), (0., 0., 1.)),
        semi_major_axis_m=(1., 1.),
        semi_minor_axis_m=(1., 1.),
        bounds=Aabb3(minimum_m=(-1., -1., -1.), maximum_m=(2., 1., 1.)),
    )
  ####
####


def testSectionedTubeRejectsUnderboundingBox(metadata_factory: MetadataFactory) -> None:
  with pytest.raises(ValidationError, match='Bounds do not enclose'):
    SectionedTubeProduct(
        metadata=metadata_factory(VISUAL_SECTIONED_TUBE_V1),
        centerline_m=((0., 0., 0.), (1., 0., 0.)),
        tangents_unit=((1., 0., 0.), (1., 0., 0.)),
        normals_unit=((0., 1., 0.), (0., 1., 0.)),
        binormals_unit=((0., 0., 1.), (0., 0., 1.)),
        semi_major_axis_m=(1., 1.),
        semi_minor_axis_m=(1., 1.),
        bounds=Aabb3(minimum_m=(0., -.5, -.5), maximum_m=(1., .5, .5)),
    )
  ####
####


def testSignatureIsIntrinsicAndShapeChecked(metadata_factory: MetadataFactory) -> None:
  product = SpectralRadiantIntensityProduct(
      metadata=metadata_factory(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
      spectral_axis=makeAxis(),
      directions_unit=((1., 0., 0.), (0., 1., 0.)),
      radiant_intensity=((10., 20.), (30., 40.)),
      value_unit='W sr^-1 m^-1',
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True, True)),
  )
  assert product.includes_range_loss is False
  assert product.includes_external_atmosphere is False
  assert product.radiant_intensity[1][1] == 40.
####


def testSignatureRejectsRangeLossAndBadShape(metadata_factory: MetadataFactory) -> None:
  base = dict(
      metadata=metadata_factory(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
      spectral_axis=makeAxis(),
      directions_unit=((1., 0., 0.),),
      radiant_intensity=((10.,),),
      value_unit='W sr^-1 m^-1',
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
  )
  with pytest.raises(ValidationError, match='literal_error'):
    SpectralRadiantIntensityProduct(**base, includes_range_loss=True)
  ####
  with pytest.raises(ValidationError, match='shape'):
    SpectralRadiantIntensityProduct(**base)
  ####
####


def testRayTransferSeparatesSourceAndTransmittance(
    metadata_factory: MetadataFactory,
) -> None:
  product = SpectralRayTransferProduct(
      metadata=metadata_factory(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
      spectral_axis=makeAxis(),
      rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
      source_radiance=((1., 2.),),
      source_radiance_unit='W m^-2 sr^-1 m^-1',
      background_transmittance=((.8, .6),),
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
  )
  background = (10., 20.)
  composed = tuple(
      background[index] * product.background_transmittance[0][index]
      + product.source_radiance[0][index]
      for index in range(2)
  )
  assert composed == pytest.approx((9., 14.))
####


def testRayTransferRejectsInvalidTransmittance(
    metadata_factory: MetadataFactory,
) -> None:
  with pytest.raises(ValidationError, match=r'\[0, 1\]'):
    SpectralRayTransferProduct(
        metadata=metadata_factory(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
        spectral_axis=makeAxis(),
        rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
        source_radiance=((1., 2.),),
        source_radiance_unit='W m^-2 sr^-1 m^-1',
        background_transmittance=((1.1, .6),),
        validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
    )
  ####
####


def testPartialBatchCannotMasqueradeAsComplete() -> None:
  with pytest.raises(ValidationError, match='complete batch'):
    BatchValidity(status=CompletionStatus.COMPLETE, valid=(True, False))
  ####
  with pytest.raises(ValidationError, match='partial batch'):
    BatchValidity(status=CompletionStatus.PARTIAL, valid=(True, True))
  ####
####
