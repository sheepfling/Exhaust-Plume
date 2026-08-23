"""Contract tests for the three independent MVP plume products."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from exhaust_plume.products import (
    Aabb3,
    BatchValidity,
    CapabilityId,
    CompletionStatus,
    CoordinateFrame,
    Fidelity,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    ProductMetadata,
    Provenance,
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


def makeMetadata(capability: CapabilityId) -> ProductMetadata:
  return ProductMetadata(
      product_id='product-001',
      capability=capability,
      snapshot_id='snapshot-001',
      time_s=0.,
      frame=CoordinateFrame(
          frame_id='vehicle',
          axis_convention='+X downstream, +Y right, +Z up',
      ),
      provenance=Provenance(
          provider_id='test-provider',
          provider_version='0.1.0',
          model_name='contract-fixture',
          model_revision='test',
      ),
      fidelity=Fidelity(
          morphology='prescribed',
          flow='none',
          radiation='none',
          time='static',
          validation='unit-test',
      ),
  )
####


def makeAxis() -> SpectralAxis:
  return SpectralAxis(
      kind=SpectralCoordinateKind.WAVELENGTH,
      values=(3.e-6, 4.e-6),
      coordinate_unit='m',
  )
####


def testCapabilityIdRoundTrip() -> None:
  capability = CapabilityId.parse('plume.visual.sectioned-tube@1')
  assert capability == VISUAL_SECTIONED_TUBE_V1
  assert str(capability) == 'plume.visual.sectioned-tube@1'
####


def testCapabilityIdRejectsMissingMajorVersion() -> None:
  with pytest.raises(ValueError):
    CapabilityId.parse('plume.visual.sectioned-tube')
  ####
####


def testSpectralAxisRejectsUnitMismatchAndNonmonotonicCoordinates() -> None:
  with pytest.raises(ValidationError):
    SpectralAxis(
        kind=SpectralCoordinateKind.WAVELENGTH,
        values=(4.e-6, 3.e-6),
        coordinate_unit='1/m',
    )
  ####
####


def testBatchValidityRequiresStatusToMatchMask() -> None:
  with pytest.raises(ValidationError):
    BatchValidity(status=CompletionStatus.COMPLETE, valid=(True, False))
  ####
  with pytest.raises(ValidationError):
    BatchValidity(status=CompletionStatus.PARTIAL, valid=(True, True))
  ####
####


def testVisualProductValidatesFramesBoundsAndFeatureChannels() -> None:
  product = SectionedTubeProduct(
      metadata=makeMetadata(VISUAL_SECTIONED_TUBE_V1),
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
              meaning='Visual diagnostic, not radiance.',
              values=(1200., 900.),
          ),
      ),
  )
  assert product.geometry_role == 'visualization'
  assert product.feature_channels[0].unit == 'K'
  invalid = product.model_dump()
  invalid['bounds'] = Aabb3(minimum_m=(0., -.1, -.1), maximum_m=(1., .1, .1))
  with pytest.raises(ValidationError):
    SectionedTubeProduct.model_validate(invalid)
  ####
####


def testSignatureProductIsIntrinsicAndShapeChecked() -> None:
  product = SpectralRadiantIntensityProduct(
      metadata=makeMetadata(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
      spectral_axis=makeAxis(),
      directions_unit=((1., 0., 0.), (0., 1., 0.)),
      radiant_intensity=((10., 12.), (8., 9.)),
      value_unit='W sr^-1 m^-1',
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True, True)),
  )
  assert product.includes_range_loss is False
  assert product.includes_external_atmosphere is False
  with pytest.raises(ValidationError):
    SpectralRadiantIntensityProduct(
        metadata=makeMetadata(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
        spectral_axis=makeAxis(),
        directions_unit=((1., 0., 0.),),
        radiant_intensity=((1.,),),
        value_unit='W sr^-1 m^-1',
        validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
    )
  ####
####


def testRayTransferSeparatesSourceRadianceAndBackgroundTransmittance() -> None:
  product = SpectralRayTransferProduct(
      metadata=makeMetadata(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
      spectral_axis=makeAxis(),
      rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
      source_radiance=((2., 3.),),
      source_radiance_unit='W m^-2 sr^-1 m^-1',
      background_transmittance=((.75, .5),),
      validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
  )
  background = (100., 200.)
  composed = tuple(
      source + transmission * incident
      for source, transmission, incident in zip(
          product.source_radiance[0],
          product.background_transmittance[0],
          background,
      )
  )
  assert composed == pytest.approx((77., 103.))
  with pytest.raises(ValidationError):
    SpectralRayTransferProduct(
        metadata=makeMetadata(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
        spectral_axis=makeAxis(),
        rays=(RayDefinition(origin_m=(0., 0., 0.), direction_unit=(1., 0., 0.)),),
        source_radiance=((2., 3.),),
        source_radiance_unit='W m^-2 sr^-1 m^-1',
        background_transmittance=((1.1, .5),),
        validity=BatchValidity(status=CompletionStatus.COMPLETE, valid=(True,)),
    )
  ####
####
