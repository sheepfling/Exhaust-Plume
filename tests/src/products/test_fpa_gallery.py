from __future__ import annotations

import json
import os
from pathlib import Path

from exhaust_plume.products import render_fpa_gallery, write_interactive_fpa_gallery
from exhaust_plume import Pose, SPECTRAL_RAY_TRANSFER_V1, SpectralRayTransferRequest
from exhaust_plume.providers import CurvedGrayRayTransferProvider
from exhaust_plume.validation import (
  DetectorResponse,
  FpaCameraOptics,
  FpaDigitizationPolicy,
  FpaPixelGeometry,
  FpaSourceReference,
  FpaVisualizationInput,
  digitize_expected_electrons,
  integrate_ray_transfer_to_fpa,
  integrate_spectral_ray_result_to_fpa,
)


def _inputs() -> FpaVisualizationInput:
  camera = FpaCameraOptics(
    camera_id='camera-gallery-test',
    focal_length_m=0.05,
    pixel_pitch_m=(5.0e-6, 5.0e-6),
    principal_point_px=(0.5, 0.5),
    aperture_area_m2=1.0e-4,
  )
  geometry = FpaPixelGeometry(
    width_px=2,
    height_px=1,
    ray_pixel_indices_row_col=((0, 0), (0, 1)),
    ray_collection_weights_m2_sr=(1.0e-6, 2.0e-6),
    camera_optics=camera,
  )
  detector = DetectorResponse(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    quantum_efficiency=(0.5, 0.6, 0.7),
    optical_throughput=(0.8, 0.9, 1.0),
    response_id='detector-gallery-test',
  )
  image = integrate_ray_transfer_to_fpa(
    detector.wavelengths_m,
    ((1.0, 2.0, 3.0), (2.0, 3.0, 4.0)),
    geometry=geometry,
    detector=detector,
    exposure_s=1.0,
  )
  policy = FpaDigitizationPolicy(
    electrons_per_count=1.0e10,
    bit_depth=12,
    policy_id='adc-gallery-test',
  )
  return FpaVisualizationInput(
    image=image,
    source=FpaSourceReference(
      capability_id='plume.optical.spectral-ray-transfer@1',
      schema_version='1.0.0',
      provider_id='provider-gallery-test',
      session_id='session-gallery-test',
      snapshot_id='snapshot-gallery-test',
      content_sha256='c' * 64,
      frame_id='sensor',
      source_status='OK',
    ),
    detector_response=detector,
    digitized=digitize_expected_electrons(image, policy=policy),
    digitization_policy=policy,
    camera_optics=camera,
  )
####


def test_static_fpa_gallery_writes_views_and_guardrails(tmp_path: Path) -> None:
  os.environ['MPLCONFIGDIR'] = str(tmp_path / 'mplconfig')
  import matplotlib
  matplotlib.use('Agg')

  manifest = render_fpa_gallery(_inputs(), tmp_path / 'fpa-gallery')
  payload = json.loads(manifest.manifest_path.read_text(encoding='utf-8'))

  assert payload['schema'] == 'plume.visualization.fpa-gallery@1'
  assert payload['source']['source']['content_sha256'] == 'c' * 64
  assert any('not_measured_detector_counts' in guard for guard in payload['guardrails'])
  assert (tmp_path / 'fpa-gallery' / 'fpa_expected_electrons.png').exists()
  assert (tmp_path / 'fpa-gallery' / 'fpa_digitized_counts.png').exists()
  assert (tmp_path / 'fpa-gallery' / 'fpa_detector_response.png').exists()
  assert (tmp_path / 'fpa-gallery' / 'fpa_pixel_values.csv').exists()
  assert all((tmp_path / 'fpa-gallery' / artifact['path']).exists() for artifact in payload['artifacts'])


def test_interactive_fpa_gallery_is_self_contained_and_exports_view_state(tmp_path: Path) -> None:
  output = write_interactive_fpa_gallery(_inputs(), tmp_path / 'fpa.html')
  html = output.read_text(encoding='utf-8')

  assert '<svg id="plot"' in html
  assert 'Export current view spec' in html
  assert 'c' * 64 in html
  assert 'fetch(' not in html
  assert 'expected_electrons' in html
  assert 'digitized_counts' in html


def test_fpa_source_reference_preserves_curved_ray_provider_identity() -> None:
  from tests.src.providers.test_curved_gray_ray_transfer import _definition

  session = CurvedGrayRayTransferProvider().create_session(definition=_definition())
  snapshot = session.create_snapshot(
    time_s=4.0,
    source_pose=Pose(frame_id='world', translation_m=(0.0, 0.0, 0.0), rotation_xyzw=(0.0, 0.0, 0.0, 1.0)),
    dynamic_state={'throttle_fraction': 0.5},
    ambient_state={'altitude_m': 1000.0},
  )
  result = snapshot.evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-1.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(5.0,),
      wavelengths_m=(1.0e-6, 2.0e-6),
    ),
  )
  source = FpaSourceReference.from_ray_result(result)
  assert source.provider_id == 'plume.curved-gray-ray-transfer'
  assert source.snapshot_id == result.metadata.snapshot.snapshot_id
  assert len(source.content_sha256) == 64
  assert source.source_provenance['provider_id'] == source.provider_id

  base = _inputs()
  integrated = integrate_spectral_ray_result_to_fpa(
    result,
    (1.0e-6, 2.0e-6),
    geometry=FpaPixelGeometry(
      width_px=1,
      height_px=1,
      ray_pixel_indices_row_col=((0, 0),),
      ray_collection_weights_m2_sr=(1.0e-6,),
      camera_optics=base.camera_optics,
    ),
    detector=DetectorResponse(
      wavelengths_m=(1.0e-6, 2.0e-6),
      quantum_efficiency=(0.5, 0.5),
      optical_throughput=(1.0, 1.0),
    ),
    exposure_s=1.0,
  )
  assert integrated.width_px == 1
  assert integrated.validity_mask == ((True,),)
