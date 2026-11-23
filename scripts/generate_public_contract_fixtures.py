from __future__ import annotations

import argparse
from pathlib import Path

from exhaust_plume.contracts import (
  ApplicabilityReport,
  ApplicabilityStatus,
  AxisymmetricZoneData,
  AxisymmetricZoneFieldResult,
  ConsistencyLevel,
  Derivation,
  ENGINEERING_FLUX_SECTION_CAPABILITY,
  EngineeringFluxSectionRequest,
  EngineeringFluxSectionResult,
  EngineeringFluxSectionSampleV1,
  GeometryClaim,
  HandoffApplicabilityV1,
  HandoffFrameV1,
  HandoffPoseV1,
  HandoffProvenanceV1,
  HandoffSpeciesMassFlowV1,
  IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
  MODEL_LANE_VISUALIZATION_CAPABILITY,
  ModelLaneField,
  ModelLaneFieldChannel,
  ModelLanePath,
  ModelLaneSectionChannel,
  ModelLaneVisualizationClaims,
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
  ModelVisualizationLaneId,
  Pose,
  PlumeFluxSectionV1,
  ProductClaims,
  ProjectedAreaResult,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SnapshotMetadata,
  SpectralSignatureResult,
  SpectralRadianceImageRequest,
  SpectralRadianceImageResult,
  SpatialSupportResult,
  SpatialLocalFieldChannel,
  SpatialLocalFieldRequest,
  SpatialLocalFieldResult,
  TimeModel,
  VersionedSpectralRayTransferResult,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  canonical_digest,
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
  VisualBounds,
  VisualSection,
  VisualSectionedTubeResult,
  VisualSectionedTubeRequest,
  VisualTubeSummary,
  VisualSampling,
)


def _snapshot() -> SnapshotMetadata:
  return SnapshotMetadata(
    snapshot_id='fixture-snapshot-1',
    session_id='fixture-session-1',
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state_digest_sha256='fixture-dynamic',
    ambient_state_digest_sha256='fixture-ambient',
    provider_state_digest_sha256='fixture-provider',
  )
####


def _metadata(
  capability: object,
  result_id: str,
  *,
  radiometric: bool,
  derivation: Derivation = Derivation.NATIVE,
) -> ResultMetadata:
  return ResultMetadata(
    capability=capability,  # type: ignore[arg-type]
    result_id=result_id,
    request_digest_sha256='fixture-request',
    snapshot=_snapshot(),
    output_frame_id='world',
    claims=ProductClaims(
      geometry=GeometryClaim.ILLUSTRATIVE if not radiometric else GeometryClaim.NOT_APPLICABLE,
      radiation=RadiationClaim.APPEARANCE_ONLY if not radiometric else RadiationClaim.SPECTRAL_ENGINEERING,
      time_model=TimeModel.STEADY,
      derivation=derivation,
      consistency=ConsistencyLevel.CO_GENERATED,
    ),
    applicability=ApplicabilityReport(status=ApplicabilityStatus.INSIDE),
    provenance=ResultProvenance(
      model_lineage_id='fixture-lineage',
      provider_id='provider.fixture',
      provider_version='1.0.0',
      configuration_digest_sha256='fixture-configuration',
    ),
  )
####


def _visual_fixture() -> VisualSectionedTubeResult:
  sections = (
    VisualSection(
      arc_length_m=0.0,
      center_m=(0.0, 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.5,
      radius_minor_m=0.3,
    ),
    VisualSection(
      arc_length_m=1.0,
      center_m=(1.0, 0.1, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.55,
      radius_minor_m=0.32,
    ),
    VisualSection(
      arc_length_m=2.0,
      center_m=(2.0, 0.2, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.6,
      radius_minor_m=0.34,
    ),
  )
  return VisualSectionedTubeResult(
    metadata=_metadata(VISUAL_SECTIONED_TUBE_CAPABILITY, 'fixture-visual-result', radiometric=False),
    sections=sections,
    channels={
      'core_radius_fraction': (1.0, 0.75, 0.5),
      'mixing_weight': (0.0, 0.5, 1.0),
    },
    visual_bounds=VisualBounds(
      minimum_m=(-0.6, -0.6, -0.6),
      maximum_m=(2.6, 0.8, 0.6),
    ),
    summary=VisualTubeSummary(length_m=2.0, maximum_radius_m=0.6, nominal_divergence_angle_rad=0.05),
  )
####


def _model_lane_visualization_fixture() -> ModelLaneVisualizationResult:
  request = ModelLaneVisualizationRequest(
    visual_request=VisualSectionedTubeRequest(
      output_frame_id='world',
      sampling=VisualSampling(maximum_section_count=3),
      requested_channels=('core_radius_fraction',),
    ),
  )
  tube = _visual_fixture()
  tube = tube.model_copy(update={
    'metadata': tube.metadata.model_copy(update={
      'request_digest_sha256': canonical_digest(request.visual_request),
    }),
  })
  metadata = _metadata(
    MODEL_LANE_VISUALIZATION_CAPABILITY,
    'fixture-model-lane-result',
    radiometric=False,
  ).model_copy(update={
    'request_digest_sha256': canonical_digest(request),
  })
  return ModelLaneVisualizationResult(
    metadata=metadata,
    lane_id=ModelVisualizationLaneId.PLANAR_MOC,
    model_id='fixture-planar-moc',
    model_version='fixture-1',
    source_status='research-only',
    applicability=metadata.applicability,
    claims=ModelLaneVisualizationClaims(
      model_fidelity='RESEARCH_ONLY',
      validation_level='UNVERIFIED',
      geometry_claim=GeometryClaim.ILLUSTRATIVE,
      production_claim_allowed=False,
      claim_notes=('synthetic contract fixture',),
    ),
    visual_request_digest_sha256=canonical_digest(request.visual_request),
    sectioned_tube=tube,
    section_channels=(
      ModelLaneSectionChannel(
        channel_id='core_radius_fraction',
        semantic='normalized core radius',
        unit='1',
        values=(1.0, 0.75, 0.5),
      ),
      ModelLaneSectionChannel(
        channel_id='mixing_weight',
        semantic='display-only synthetic mixing weight',
        unit='1',
        values=(0.0, 0.5, 1.0),
      ),
    ),
    paths=(ModelLanePath(
      path_id='fixture-centerline',
      semantic='retained illustrative centerline',
      points_m=((0.0, 0.0, 0.0), (1.0, 0.1, 0.0), (2.0, 0.2, 0.0)),
    ),),
    fields=(ModelLaneField(
      field_id='fixture-cells',
      semantic='retained research cell field',
      polygons_xr_m=(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),),
      channels={
        'mach': ModelLaneFieldChannel(
          semantic='cell Mach number',
          unit='1',
          values=(2.0,),
        ),
      },
      region_types=('expansion',),
      region_labels=('cell-0',),
    ),),
    diagnostics={'fixture': True},
    warnings=('synthetic contract fixture; not physical evidence',),
  )
####


def _signature_fixture() -> SpectralSignatureResult:
  return SpectralSignatureResult(
    metadata=_metadata(SPECTRAL_RADIANT_INTENSITY_CAPABILITY, 'fixture-signature-result', radiometric=True),
    spectral_radiant_intensity=((1.0, 0.5), (0.8, 0.4)),
    validity_mask=((True, True), (True, True)),
    direction_status=(
      SampleStatus(code=SampleStatusCode.OK),
      SampleStatus(code=SampleStatusCode.OK),
    ),
    absolute_standard_uncertainty=((0.1, 0.05), (0.08, 0.04)),
  )
####


def _ray_fixture() -> VersionedSpectralRayTransferResult:
  return VersionedSpectralRayTransferResult(
    metadata=_metadata(SPECTRAL_RAY_TRANSFER_CAPABILITY, 'fixture-ray-result', radiometric=True),
    source_spectral_radiance=((0.0, 0.0), (2.0, 1.0)),
    absolute_standard_uncertainty=((None, None), (0.2, 0.1)),
    background_transmittance=((1.0, 1.0), (0.25, 0.5)),
    validity_mask=((True, True), (True, True)),
    ray_status=(
      SampleStatus(code=SampleStatusCode.OK),
      SampleStatus(code=SampleStatusCode.OK),
    ),
    hit_mask=(False, True),
    optical_depth=((0.0, 0.0), (1.3862943611198906, 0.6931471805599453)),
    plume_intersection_t_m=(None, (2.0, 4.0)),
  )
####


def _spectral_radiance_image_fixture() -> SpectralRadianceImageResult:
  ray_result = _ray_fixture()
  request = SpectralRadianceImageRequest(
    pixel_frame_id='fixture-pixel-frame',
    ray_frame_id='world',
    ray_transfer_request_digest_sha256='a' * 64,
    ray_transfer_result_id=ray_result.metadata.result_id,
    ray_transfer_result_digest_sha256=canonical_digest(ray_result),
    pixel_geometry_sha256='b' * 64,
    width_px=1,
    height_px=1,
    ray_pixel_indices_row_col=((0, 0), (0, 0)),
    ray_collection_weights_m2_sr=(1.0e-6, 2.0e-6),
  )
  image_request_digest = canonical_digest(request)
  metadata = _metadata(
    IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
    'fixture-spectral-radiance-image-result',
    radiometric=True,
    derivation=Derivation.ADAPTED,
  ).model_copy(update={
    'request_digest_sha256': image_request_digest,
    'output_frame_id': request.pixel_frame_id,
    'provenance': _metadata(
      IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
      'fixture-image-lineage',
      radiometric=True,
    ).provenance.model_copy(update={
      'parent_result_ids': (ray_result.metadata.result_id,),
      'metadata': {
        'source_fixture': 'synthetic',
        'pixel_geometry_sha256': request.pixel_geometry_sha256,
        'ray_transfer_request_digest_sha256': request.ray_transfer_request_digest_sha256,
        'ray_transfer_result_digest_sha256': request.ray_transfer_result_digest_sha256,
        'spectral_radiance_image_request_digest_sha256': image_request_digest,
      },
    }),
  })
  return SpectralRadianceImageResult(
    metadata=metadata,
    pixel_frame_id=request.pixel_frame_id,
    ray_frame_id=request.ray_frame_id,
    ray_transfer_request_digest_sha256=request.ray_transfer_request_digest_sha256,
    ray_transfer_result_id=request.ray_transfer_result_id,
    ray_transfer_result_digest_sha256=request.ray_transfer_result_digest_sha256,
    pixel_geometry_sha256=request.pixel_geometry_sha256,
    width_px=request.width_px,
    height_px=request.height_px,
    wavelengths_m=(1.0e-6, 2.0e-6),
    source_spectral_radiance_W_m2_sr_m=(((4.0 / 3.0, 2.0 / 3.0),),),
    background_transmittance=(((0.5, 2.0 / 3.0),),),
    validity_mask=((True,),),
    pixel_status=((SampleStatus(code=SampleStatusCode.OK),),),
    ray_sample_count=((2,),),
    pixel_collection_weight_m2_sr=((3.0e-6,),),
  )
####


def _spatial_support_fixture() -> SpatialSupportResult:
  return SpatialSupportResult(
    metadata=_metadata(SPATIAL_SUPPORT_CAPABILITY, 'fixture-support-result', radiometric=False),
    plume_frame_aabb_min_m=(0.0, -0.5, -0.5),
    plume_frame_aabb_max_m=(2.0, 0.5, 0.5),
    characteristic_extent_m=2.0,
    support_definition='finite provider-declared support bounds',
    is_conservative=True,
  )
####


def _projected_area_fixture() -> ProjectedAreaResult:
  return ProjectedAreaResult(
    metadata=_metadata(SPATIAL_PROJECTED_AREA_CAPABILITY, 'fixture-area-result', radiometric=False),
    reference_area_m2=0.75,
    closed_zone_count=3,
  )
####


def _axisymmetric_zone_field_fixture() -> AxisymmetricZoneFieldResult:
  return AxisymmetricZoneFieldResult(
    metadata=_metadata(
      SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
      'fixture-zone-field-result',
      radiometric=False,
    ),
    axis_definition='x-axis; r is non-negative radial distance',
    zones=(
      AxisymmetricZoneData(
        zone_id='fixture-isentropic-region',
        polygon_xr_m=((0.0, 0.0), (1.0, 0.0), (1.0, 0.2), (0.0, 0.2)),
        static_pressure_Pa=180_000.0,
        static_temperature_K=1200.0,
        density_kgpm3=0.4,
        mach=2.1,
        phase='Isentropic',
        cell_index=0,
        region_type='Isentropic',
        region_label='Exit state',
      ),
      AxisymmetricZoneData(
        zone_id='fixture-compression-region',
        polygon_xr_m=((1.0, 0.0), (2.0, 0.0), (2.0, 0.3), (1.0, 0.2)),
        static_pressure_Pa=220_000.0,
        static_temperature_K=1350.0,
        density_kgpm3=0.5,
        mach=1.8,
        phase='ObliqueShock',
        cell_index=0,
        region_type='ObliqueShock',
        region_label='Centerline compression',
        shock_angle_rad=0.34702962104132495,
        turn_angle_rad=0.010599288423643438,
      ),
    ),
  )
####


def _spatial_local_field_fixture() -> SpatialLocalFieldResult:
  request = SpatialLocalFieldRequest(
    coordinate_frame_id='world',
    points_m=((0.5, 0.0, 0.0), (1.0, 0.1, 0.0)),
    field_ids=('static-pressure', 'temperature'),
  )
  return SpatialLocalFieldResult(
    metadata=_metadata(
      SPATIAL_LOCAL_FIELD_CAPABILITY,
      'fixture-local-field-result',
      radiometric=False,
    ).model_copy(update={'request_digest_sha256': canonical_digest(request)}),
    coordinate_frame_id=request.coordinate_frame_id,
    points_m=request.points_m,
    field_ids=request.field_ids,
    channels=(
      SpatialLocalFieldChannel(
        field_id='static-pressure',
        semantic='static pressure',
        unit='Pa',
        sampling_method='point-evaluation',
        values=(180_000.0, 195_000.0),
        sample_status=(SampleStatus(code=SampleStatusCode.OK),) * 2,
        absolute_standard_uncertainty=(100.0, 120.0),
      ),
      SpatialLocalFieldChannel(
        field_id='temperature',
        semantic='static temperature',
        unit='K',
        sampling_method='provider-interpolated',
        values=(1200.0, 1250.0),
        sample_status=(SampleStatus(code=SampleStatusCode.OK),) * 2,
      ),
    ),
  )
####


def _plume_flux_section_fixture() -> PlumeFluxSectionV1:
  identity_pose = HandoffPoseV1(
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  return PlumeFluxSectionV1(
    time_s=0.0,
    frame=HandoffFrameV1(
      frame_id='plume-local',
      parent_frame_id='world',
      pose_parent_from_frame=identity_pose,
    ),
    section_pose=identity_pose,
    center_m=(0.0, 0.0, 0.0),
    normal=(1.0, 0.0, 0.0),
    area_m2=0.2,
    mass_flow_kg_s=1.5,
    momentum_flux_N=(60.0, 0.0, 0.0),
    advective_momentum_flux_N=(60.0, 0.0, 0.0),
    pressure_thrust_N=(0.0, 0.0, 0.0),
    stagnation_enthalpy_flux_W=800_000.0,
    species_mass_flows_kg_s=(HandoffSpeciesMassFlowV1(species_id='exhaust', mass_flow_kg_s=1.5),),
    pressure_Pa=101_325.0,
    ambient_pressure_Pa=101_325.0,
    pressure_match_relative_residual=0.0,
    cross_section_second_moment_m2=((0.01, 0.0), (0.0, 0.01)),
    characteristic_radius_m=0.252313252202016,
    provenance=HandoffProvenanceV1(
      model_id='fixture-source',
      model_version='1.0.0',
      code_revision='fixture-revision',
      configuration_sha256='3' * 64,
    ),
    applicability=HandoffApplicabilityV1(
      supported=True,
      domain={'mach': [2.0, 3.0]},
    ),
    uncertainty={'mass_flow_kg_s': 0.01, 'pressure_Pa': 50.0},
  )
####


def _engineering_flux_section_fixture() -> EngineeringFluxSectionResult:
  request = EngineeringFluxSectionRequest(
    output_frame_id='plume-local',
    centerline_reference_id='fixture-source-centerline',
    centerline_arclength_m=(0.0,),
  )
  base_metadata = _metadata(
    ENGINEERING_FLUX_SECTION_CAPABILITY,
    'fixture-engineering-flux-result',
    radiometric=False,
  )
  metadata = ResultMetadata.model_validate({
    **base_metadata.model_dump(mode='python'),
    'request_digest_sha256': canonical_digest(request),
    'output_frame_id': request.output_frame_id,
    'provenance': {
      **base_metadata.provenance.model_dump(mode='python'),
      'metadata': {'centerline_reference_id': request.centerline_reference_id},
    },
  })
  return EngineeringFluxSectionResult(
    metadata=metadata,
    request=request,
    samples=(
      EngineeringFluxSectionSampleV1(
        station_arclength_m=0.0,
        centerline_position_m=(0.0, 0.0, 0.0),
        centerline_tangent=(1.0, 0.0, 0.0),
        sampling_method='native',
        status=SampleStatus(code=SampleStatusCode.OK),
        section=_plume_flux_section_fixture(),
      ),
    ),
  )
####


def main() -> None:
  parser = argparse.ArgumentParser(description='Export neutral public plume contract fixtures.')
  parser.add_argument('directory', nargs='?', default='fixtures/contracts')
  arguments = parser.parse_args()
  output_directory = Path(arguments.directory)
  output_directory.mkdir(parents=True, exist_ok=True)
  fixtures = {
    'visual_sectioned_tube_v1.json': _visual_fixture(),
    'spectral_signature_v1.json': _signature_fixture(),
    'spectral_ray_transfer_v1.json': _ray_fixture(),
    'spectral_radiance_image_result_v1.json': _spectral_radiance_image_fixture(),
    'spatial_support_result_v1.json': _spatial_support_fixture(),
    'projected_area_result_v1.json': _projected_area_fixture(),
    'axisymmetric_zone_field_result_v1.json': _axisymmetric_zone_field_fixture(),
    'spatial_local_field_result_v1.json': _spatial_local_field_fixture(),
    'plume_flux_section_v1.json': _plume_flux_section_fixture(),
    'engineering_flux_section_result_v1.json': _engineering_flux_section_fixture(),
  }
  for name, model in fixtures.items():
    path = output_directory / name
    path.write_text(model.model_dump_json(indent=2) + '\n', encoding='utf-8')
    print(path)
  ####
  invalid_visual = _visual_fixture().model_dump(mode='json')
  invalid_visual['sections'][1]['arc_length_m'] = 0.0
  invalid_path = output_directory / 'invalid_visual_nonmonotonic.json'
  import json
  invalid_path.write_text(json.dumps(invalid_visual, indent=2) + '\n', encoding='utf-8')
  print(invalid_path)
####


if __name__ == '__main__':
  main()
####
