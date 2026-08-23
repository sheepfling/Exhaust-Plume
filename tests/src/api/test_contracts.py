from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from exhaust_plume.api import (
    ENGINEERING_FLUX_SECTION_V1,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    Applicability,
    FeatureAssociation,
    FeatureChannel,
    FidelityClaim,
    FrameRef,
    ItemStatus,
    ModelFidelity,
    PlumeFluxSection,
    PlumeFluxSectionResult,
    Pose3,
    Provenance,
    ResultEnvelope,
    ResultStatus,
    SectionedTubePayload,
    SnapshotRequest,
    SpeciesMassFlow,
    SpectralRayTransferPayload,
    SupportDefinition,
    TimeAccessPolicy,
    TubeSection,
    ValidationLevel,
    calculate_content_sha256,
)


def _identity_pose() -> Pose3:
  return Pose3(
      translation_m=(0., 0., 0.),
      rotation_xyzw=(0., 0., 0., 1.),
  )
####


def _frame() -> FrameRef:
  return FrameRef(
      frame_id='aircraft-body',
      parent_frame_id=None,
      pose_parent_from_frame=_identity_pose(),
  )
####


def _provenance() -> Provenance:
  return Provenance(
      model_id='test-fixture',
      model_version='1.0.0',
      code_revision='test',
      configuration_sha256='0' * 64,
  )
####


def _envelope(capability_id: str) -> ResultEnvelope:
  return ResultEnvelope(
      capability_id=capability_id,
      schema_version='1.0.0',
      provider_id=uuid4(),
      session_id=uuid4(),
      snapshot_id=uuid4(),
      content_sha256='1' * 64,
      requested_time_s=0.,
      actual_time_s=0.,
      frame=_frame(),
      status=ResultStatus.OK,
      fidelity=FidelityClaim(
          model_fidelity=ModelFidelity.PRESCRIBED,
          validation_level=ValidationLevel.VERIFIED,
      ),
      applicability=Applicability(supported=True),
      provenance=_provenance(),
  )
####


def _sections() -> tuple[TubeSection, TubeSection]:
  return (
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
          center_m=(1., 0., 0.),
          tangent=(1., 0., 0.),
          normal_1=(0., 1., 0.),
          normal_2=(0., 0., 1.),
          semi_axis_1_m=.3,
          semi_axis_2_m=.3,
      ),
  )
####


def test_section_frame_requires_right_handed_orthonormal_basis() -> None:
  with pytest.raises(ValidationError, match='right-handed'):
    TubeSection(
        arc_length_m=0.,
        center_m=(0., 0., 0.),
        tangent=(1., 0., 0.),
        normal_1=(0., 1., 0.),
        normal_2=(0., 0., -1.),
        semi_axis_1_m=.2,
        semi_axis_2_m=.2,
    )
  ####
####


def test_sectioned_tube_feature_channel_shape_is_explicit() -> None:
  with pytest.raises(ValidationError, match='expected 2'):
    SectionedTubePayload(
        sections=_sections(),
        feature_channels=(
            FeatureChannel(
                channel_id='temperature',
                semantic='temperature',
                unit='K',
                association=FeatureAssociation.SECTION,
                component_count=1,
                values=(600.,),
            ),
        ),
        support_definition=SupportDefinition(
            kind='ENCLOSED_EXHAUST_MASS_FRACTION',
            fraction=.95,
        ),
    )
  ####
####


def test_ray_transfer_requires_values_to_match_validity_mask() -> None:
  with pytest.raises(ValidationError, match='validity_mask'):
    SpectralRayTransferPayload(
        ray_ids=('ray-1',),
        origins_m=((0., 0., 0.),),
        directions=((1., 0., 0.),),
        wavelengths_m=(3.e-6, 5.e-6),
        source_radiance_W_m2_sr_m=((1., None),),
        background_transmittance=((.9, None),),
        validity_mask=((True, True),),
        item_status=(ItemStatus.OK,),
    )
  ####
####


def test_flux_section_checks_pressure_residual_and_second_moment() -> None:
  section = PlumeFluxSection(
      time_s=0.,
      frame=_frame(),
      section_pose=_identity_pose(),
      normal=(1., 0., 0.),
      area_m2=.2,
      mass_flow_kgps=1.5,
      momentum_flux_N=(60., 0., 0.),
      total_energy_flow_W=8.e5,
      species_mass_flows_kgps=(SpeciesMassFlow(species_id='exhaust', mass_flow_kgps=1.5),),
      pressure_Pa=101325.,
      ambient_pressure_Pa=101325.,
      pressure_match_relative_residual=0.,
      cross_section_second_moment_m2=((.01, 0.), (0., .01)),
      provenance=_provenance(),
      applicability=Applicability(supported=True),
  )
  result = PlumeFluxSectionResult(
      envelope=_envelope(ENGINEERING_FLUX_SECTION_V1),
      payload=section,
  )
  assert result.payload.mass_flow_kgps == 1.5

  invalid = section.model_dump(mode='python')
  invalid['pressure_match_relative_residual'] = .1
  with pytest.raises(ValidationError, match='pressure_match_relative_residual'):
    PlumeFluxSection.model_validate(invalid)
  ####
####


def test_content_hash_is_deterministic_and_json_safe() -> None:
  payload = SectionedTubePayload(
      sections=_sections(),
      support_definition=SupportDefinition(kind='INTEGRAL_TOP_HAT_BOUNDARY'),
  )
  assert calculate_content_sha256(payload) == calculate_content_sha256(payload.model_copy(deep=True))
  assert len(calculate_content_sha256(payload)) == 64
####


def test_snapshot_request_defaults_to_exact() -> None:
  request = SnapshotRequest(time_s=12.)
  assert request.time_policy is TimeAccessPolicy.EXACT
####


def test_product_capability_mismatch_is_rejected() -> None:
  payload = SpectralRayTransferPayload(
      ray_ids=('ray-1',),
      origins_m=((0., 0., 0.),),
      directions=((1., 0., 0.),),
      wavelengths_m=(3.e-6,),
      source_radiance_W_m2_sr_m=((1.,),),
      background_transmittance=((.9,),),
      validity_mask=((True,),),
      item_status=(ItemStatus.OK,),
  )
  from exhaust_plume.api import SpectralRayTransferResult

  with pytest.raises(ValidationError, match='capability_id'):
    SpectralRayTransferResult(
        envelope=_envelope(OPTICAL_SPECTRAL_RAY_TRANSFER_V1 + '-wrong'),
        payload=payload,
    )
  ####
####


def test_public_result_json_schemas_generate() -> None:
  from exhaust_plume.api import (
      PlumeFluxSectionResult,
      SectionedTubeResult,
      SpectralRadiantIntensityResult,
      SpectralRayTransferResult,
  )

  for model in (
      SectionedTubeResult,
      SpectralRadiantIntensityResult,
      SpectralRayTransferResult,
      PlumeFluxSectionResult,
  ):
    schema = model.model_json_schema()
    assert schema['type'] == 'object'
  ####
####
