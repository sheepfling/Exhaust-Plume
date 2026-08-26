from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from exhaust_plume.api import (
  ENGINEERING_FLUX_SECTION_V1,
  OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
  SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
  Applicability,
  FidelityClaim,
  FrameRef,
  InvalidSamplePolicy,
  ItemStatus,
  ModelFidelity,
  PlumeFluxSection,
  PlumeFluxSectionResult,
  Pose3,
  Provenance,
  ResultEnvelope,
  ResultStatus,
  SpectralRadiantIntensityPayload,
  SpectralRadiantIntensityResult,
  SpectralRayTransferPayload,
  SpectralRayTransferResult,
  ValidationLevel,
  ViewSelection,
  VisualizationSpec,
  project_plume_flux_view,
  project_sectioned_tube_view,
  project_spectral_radiant_intensity_view,
  project_spectral_ray_transfer_view,
)
from exhaust_plume.products import (
  render_product_gallery,
)

ROOT = Path(__file__).resolve().parents[3]


def _frame() -> FrameRef:
  return FrameRef(
    frame_id='aircraft-body',
    parent_frame_id=None,
    pose_parent_from_frame=Pose3(
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
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
    requested_time_s=0.0,
    actual_time_s=0.0,
    frame=_frame(),
    status=ResultStatus.OK,
    fidelity=FidelityClaim(
      model_fidelity=ModelFidelity.PRESCRIBED,
      validation_level=ValidationLevel.VERIFIED,
    ),
    applicability=Applicability(supported=True),
    provenance=Provenance(
      model_id='gallery-test',
      model_version='1.0.0',
      code_revision='test',
      configuration_sha256='2' * 64,
    ),
  )
####


def _visual_result():
  fixture_path = ROOT / 'tests' / 'fixtures' / 'sectioned_tube_washed_v1.json'
  from exhaust_plume.api import SectionedTubeResult
  return SectionedTubeResult.model_validate_json(fixture_path.read_text(encoding='utf-8'))
####


def _signature_result() -> SpectralRadiantIntensityResult:
  return SpectralRadiantIntensityResult(
    envelope=_envelope(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
    payload=SpectralRadiantIntensityPayload(
      directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
      wavelengths_m=(3.0e-6, 5.0e-6),
      radiant_intensity_W_sr_m=((1.0, None), (0.5, 0.25), (0.2, 0.4)),
      validity_mask=((True, False), (True, True), (True, True)),
      uncertainty={'source': 'synthetic'},
    ),
  )
####


def _ray_result() -> SpectralRayTransferResult:
  return SpectralRayTransferResult(
    envelope=_envelope(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
    payload=SpectralRayTransferPayload(
      ray_ids=('ray-1', 'ray-2'),
      origins_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
      directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
      wavelengths_m=(3.0e-6, 5.0e-6),
      source_radiance_W_m2_sr_m=((1.0, None), (0.0, 2.0)),
      background_transmittance=((0.8, None), (1.0, 0.5)),
      validity_mask=((True, False), (True, True)),
      item_status=(ItemStatus.OK, ItemStatus.OK),
    ),
  )
####


def _flux_result() -> PlumeFluxSectionResult:
  return PlumeFluxSectionResult(
    envelope=_envelope(ENGINEERING_FLUX_SECTION_V1),
    payload=PlumeFluxSection(
      time_s=4.0,
      frame=_frame(),
      section_pose=Pose3(
        translation_m=(1.0, 2.0, 3.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      normal=(1.0, 0.0, 0.0),
      area_m2=0.2,
      mass_flow_kgps=1.5,
      momentum_flux_N=(60.0, 2.0, 3.0),
      total_energy_flow_W=8.0e5,
      species_mass_flows_kgps=(
        {'species_id': 'exhaust', 'mass_flow_kgps': 1.5},
        {'species_id': 'air', 'mass_flow_kgps': 0.2},
      ),
      pressure_Pa=101325.0,
      ambient_pressure_Pa=101325.0,
      pressure_match_relative_residual=0.0,
      cross_section_second_moment_m2=((0.01, 0.0), (0.0, 0.02)),
      provenance=Provenance(
        model_id='gallery-test',
        model_version='1.0.0',
        code_revision='test',
        configuration_sha256='3' * 64,
      ),
      applicability=Applicability(supported=True),
    ),
  )
####


def test_product_projections_resolve_linked_selections() -> None:
  visual = _visual_result()
  visual_spec = VisualizationSpec.for_result(
    visual,
    view_kind='visual.station-inspector',
    selection=ViewSelection(station_index=2, channel_id='temperature', component_index=0),
  )
  visual_view = project_sectioned_tube_view(visual, visual_spec)
  assert visual_view.station_index == 2
  assert visual_view.selected_channel is not None
  assert visual_view.selected_channel.channel_id == 'temperature'

  signature = _signature_result()
  signature_view = project_spectral_radiant_intensity_view(
    signature,
    VisualizationSpec.for_result(
      signature,
      view_kind='signature.direction-spectrum',
      selection=ViewSelection(direction_index=1, wavelength_index=0),
    ),
  )
  assert signature_view.selected_direction == (0.0, 1.0, 0.0)
  assert signature_view.selected_wavelength_m == 3.0e-6

  ray = _ray_result()
  ray_view = project_spectral_ray_transfer_view(
    ray,
    VisualizationSpec.for_result(
      ray,
      view_kind='ray-transfer.ray-inspector',
      selection=ViewSelection(ray_id='ray-2', wavelength_index=1),
      ray_display_length_m=4.0,
    ),
  )
  assert ray_view.selected_line.ray_id == 'ray-2'
  assert ray_view.selected_wavelength_m == 5.0e-6

  flux = _flux_result()
  flux_view = project_plume_flux_view(
    flux,
    VisualizationSpec.for_result(
      flux,
      view_kind='flux.section-inspector',
      selection=ViewSelection(component_index=1),
    ),
  )
  assert flux_view.selected_species == ('air', 0.2)
####


@pytest.mark.parametrize(
  'result_factory',
  (_visual_result, _signature_result, _ray_result, _flux_result),
)
def test_static_gallery_dispatches_all_standard_results(result_factory, tmp_path: Path) -> None:
  os.environ['MPLCONFIGDIR'] = str(tmp_path / 'mplconfig')
  import matplotlib
  matplotlib.use('Agg')

  result = result_factory()
  output = tmp_path / result.envelope.capability_id.replace('.', '_')
  manifest = render_product_gallery(result, output)
  payload = json.loads(manifest.manifest_path.read_text(encoding='utf-8'))

  assert manifest.manifest_path == output / 'gallery_manifest.json'
  assert payload['view_spec_digest_sha256'] == manifest.view_spec.digest_sha256()
  assert payload['source']['content_sha256'] == result.envelope.content_sha256
  assert payload['source']['fidelity']['validation_level'] == 'VERIFIED'
  assert payload['artifacts']
  assert all((output / artifact['path']).exists() for artifact in payload['artifacts'])
  spec_payload = json.loads((output / 'visualization_spec.json').read_text(encoding='utf-8'))
  assert spec_payload['view_spec_digest_sha256'] == manifest.view_spec.digest_sha256()
  assert spec_payload['source']['content_sha256'] == result.envelope.content_sha256
####


def test_gallery_reject_policy_never_converts_invalid_samples_to_zero(tmp_path: Path) -> None:
  result = _signature_result()
  spec = VisualizationSpec.for_result(
    result,
    view_kind='signature.gallery',
    invalid_sample_policy=InvalidSamplePolicy.REJECT,
  )
  with pytest.raises(ValueError, match='invalid sample'):
    render_product_gallery(result, tmp_path, spec=spec)
####


def test_ray_gallery_manifest_records_non_inference_guardrails(tmp_path: Path) -> None:
  result = _ray_result()
  manifest = render_product_gallery(result, tmp_path)
  assert any('hit_miss_intersections' in guardrail for guardrail in manifest.guardrails)
  assert all('hit' not in artifact.view_id for artifact in manifest.artifacts)
