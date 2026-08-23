from __future__ import annotations

import argparse
from pathlib import Path

from exhaust_plume.contracts import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  Pose,
  ProductClaims,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SnapshotMetadata,
  SpectralSignatureResult,
  TimeModel,
  VersionedSpectralRayTransferResult,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  VisualBounds,
  VisualSection,
  VisualSectionedTubeResult,
  VisualTubeSummary,
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


def _metadata(capability: object, result_id: str, *, radiometric: bool) -> ResultMetadata:
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
      derivation=Derivation.NATIVE,
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
