from __future__ import annotations

import json
import os
from pathlib import Path

from exhaust_plume.products import render_fpa_gallery, write_interactive_fpa_gallery
from exhaust_plume.validation import (
  DetectorResponse,
  FpaCameraOptics,
  FpaDigitizationPolicy,
  FpaPixelGeometry,
  FpaSourceReference,
  FpaVisualizationInput,
  digitize_expected_electrons,
  integrate_ray_transfer_to_fpa,
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
