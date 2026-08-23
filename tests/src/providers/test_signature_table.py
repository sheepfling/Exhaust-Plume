from __future__ import annotations

import pytest

from exhaust_plume.contracts import (
  Pose,
  ProductOutsideApplicabilityError,
  ProviderConfigurationError,
  RadiationClaim,
  SampleStatusCode,
  SpectralSignatureRequest,
  TimeModel,
)
from exhaust_plume.contracts.errors import ProviderClosedError
from exhaust_plume.contracts.specs_v1 import SPECTRAL_RADIANT_INTENSITY_V1
from exhaust_plume.providers import (
  LookupInterpolationPolicy,
  SignatureTableConfiguration,
  SignatureTableDefinition,
  SignatureTableProvider,
)


def _definition() -> SignatureTableDefinition:
  return SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    direction_cosine_nodes=(-0.5, 0.0, 0.5),
    spectral_radiant_intensity_w_sr_m=(
      (0.5, 1.5, 2.5),
      (1.0, 2.0, 3.0),
      (1.5, 2.5, 3.5),
    ),
    absolute_standard_uncertainty_w_sr_m=(
      (0.05, 0.05, 0.05),
      (0.1, 0.1, 0.1),
      (0.15, 0.15, 0.15),
    ),
  )


def _snapshot(
    definition: SignatureTableDefinition | None = None,
    configuration: SignatureTableConfiguration | None = None,
    time_s: float = 0.0,
):
  return SignatureTableProvider(configuration).create_session(
    definition=definition or _definition(),
  ).create_snapshot(
    time_s=time_s,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )


def test_signature_table_interpolates_angle_and_wavelength_axes() -> None:
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((0.5, 3**0.5 / 2.0, 0.0), (0.0, 1.0, 0.0)),
    wavelengths_m=(1.5e-6, 2.5e-6),
  )
  result = _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)
  assert result.spectral_radiant_intensity == ((2.0, 3.0), (1.5, 2.5))
  assert result.validity_mask == ((True, True), (True, True))
  assert all(status.code is SampleStatusCode.OK for status in result.direction_status)
  assert result.absolute_standard_uncertainty == ((0.15, 0.15), (0.1, 0.1))
  assert result.metadata.provenance.asset_digests_sha256
  assert result.metadata.provenance.provider_id == 'signature.table-lookup'
  assert result.metadata.claims.radiation is RadiationClaim.TABULATED


def test_signature_table_preserves_axisymmetric_direction_convention() -> None:
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=(
      (0.5, 3**0.5 / 2.0, 0.0),
      (0.5, 0.0, 3**0.5 / 2.0),
    ),
    wavelengths_m=(2.0e-6,),
  )
  result = _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)
  assert result.spectral_radiant_intensity[0] == result.spectral_radiant_intensity[1]
  assert result.metadata.provenance.metadata['coordinate_convention'].startswith('direction cosine')


def test_signature_table_honors_explicit_interpolation_policies() -> None:
  definition = SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 9.0e-6),
    direction_cosine_nodes=(-0.5, 0.5),
    spectral_radiant_intensity_w_sr_m=((1.0, 9.0), (1.0, 9.0)),
    wavelength_interpolation=LookupInterpolationPolicy.LOG_LINEAR,
    angular_interpolation=LookupInterpolationPolicy.NEAREST,
  )
  result = _snapshot(definition).evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((0.0, 1.0, 0.0),),
    wavelengths_m=(3.0e-6,),
  ))
  assert result.spectral_radiant_intensity[0][0] == pytest.approx(3.0**0.5)
  assert result.metadata.provenance.metadata['interpolation_wavelength'] == 'log-linear'
  assert result.metadata.provenance.metadata['interpolation_angular'] == 'nearest'

  exact_definition = SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 2.0e-6),
    direction_cosine_nodes=(-0.5, 0.5),
    spectral_radiant_intensity_w_sr_m=((1.0, 2.0), (1.0, 2.0)),
    wavelength_interpolation=LookupInterpolationPolicy.EXACT_ONLY,
  )
  with pytest.raises(ProductOutsideApplicabilityError, match='exact table nodes'):
    _snapshot(exact_definition).evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((-0.5, 3**0.5 / 2.0, 0.0),),
      wavelengths_m=(1.5e-6,),
    ))


def test_signature_table_interpolates_optional_time_axis() -> None:
  definition = SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 2.0e-6),
    direction_cosine_nodes=(-0.5, 0.5),
    spectral_radiant_intensity_w_sr_m=((1.0, 2.0), (2.0, 3.0)),
    absolute_standard_uncertainty_w_sr_m=((0.1, 0.1), (0.2, 0.2)),
    time_nodes_s=(0.0, 1.0),
    spectral_radiant_intensity_w_sr_m_by_time=(
      ((1.0, 2.0), (2.0, 3.0)),
      ((3.0, 4.0), (4.0, 5.0)),
    ),
    absolute_standard_uncertainty_w_sr_m_by_time=(
      ((0.1, 0.1), (0.2, 0.2)),
      ((0.3, 0.3), (0.4, 0.4)),
    ),
  )
  configuration = SignatureTableConfiguration(time_model=TimeModel.PRESCRIBED_TRANSIENT)
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((0.0, 1.0, 0.0),),
    wavelengths_m=(1.5e-6,),
  )
  result = _snapshot(definition, configuration, time_s=0.5).evaluate(
    SPECTRAL_RADIANT_INTENSITY_V1,
    request,
  )
  assert result.spectral_radiant_intensity[0][0] == pytest.approx(3.0)
  assert result.absolute_standard_uncertainty is not None
  assert result.absolute_standard_uncertainty[0][0] == pytest.approx(0.25)
  assert result.metadata.claims.time_model is TimeModel.PRESCRIBED_TRANSIENT
  assert result.metadata.provenance.metadata['time_domain'] == '[0, 1] s'

  with pytest.raises(ProductOutsideApplicabilityError, match='temporal table domain'):
    _snapshot(definition, configuration, time_s=2.0).evaluate(
      SPECTRAL_RADIANT_INTENSITY_V1,
      request,
    )
  with pytest.raises(ProviderConfigurationError, match='prescribed_transient'):
    _snapshot(definition)


def test_signature_table_rejects_extrapolation_by_default() -> None:
  with pytest.raises(ProductOutsideApplicabilityError, match='outside the angular'):
    _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((1.0, 0.0, 0.0),),
      wavelengths_m=(2.0e-6,),
    ))


def test_signature_table_binds_an_optional_operating_point_id() -> None:
  with pytest.raises(ProductOutsideApplicabilityError, match='operating point'):
    _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
      direction_frame_id='source-local',
      operating_point_id='different-condition',
      source_to_observer_directions=((0.0, 1.0, 0.0),),
      wavelengths_m=(2.0e-6,),
    ))
  with pytest.raises(ProductOutsideApplicabilityError, match='outside the table'):
    _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((0.0, 1.0, 0.0),),
      wavelengths_m=(4.0e-6,),
    ))


def test_signature_table_supports_explicit_partial_direction_results() -> None:
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    wavelengths_m=(2.0e-6,),
    allow_partial_results=True,
  )
  result = _snapshot().evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)
  assert result.direction_status[0].code is SampleStatusCode.OUTSIDE_APPLICABILITY
  assert result.validity_mask[0] == (False,)
  assert result.spectral_radiant_intensity[0] == (0.0,)
  assert result.direction_status[1].code is SampleStatusCode.OK
  assert result.metadata.applicability.status.value == 'marginal'


def test_signature_table_validates_frame_and_lifetime() -> None:
  session = SignatureTableProvider().create_session(definition=_definition())
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  with pytest.raises(ProductOutsideApplicabilityError, match='direction frame'):
    snapshot.evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
      direction_frame_id='other-frame',
      source_to_observer_directions=((0.0, 1.0, 0.0),),
      wavelengths_m=(2.0e-6,),
    ))
  session.close()
  with pytest.raises(ProviderClosedError):
    session.create_snapshot(
      time_s=0.0,
      source_pose=Pose(
        frame_id='world',
        translation_m=(0.0, 0.0, 0.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      dynamic_state={},
      ambient_state={},
    )
  from exhaust_plume.providers import SignatureTableConfiguration
  extrapolating_snapshot = SignatureTableProvider(
    SignatureTableConfiguration(allow_extrapolation=True),
  ).create_session(definition=_definition()).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  extrapolated = extrapolating_snapshot.evaluate(SPECTRAL_RADIANT_INTENSITY_V1, SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((1.0, 0.0, 0.0),),
    wavelengths_m=(4.0e-6,),
  ))
  assert extrapolated.spectral_radiant_intensity == ((5.0,),)
  assert extrapolated.metadata.warnings == ('explicit table extrapolation enabled',)
  assert extrapolated.metadata.applicability.status.value == 'marginal'
