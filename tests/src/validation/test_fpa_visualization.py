from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume.api import InvalidSamplePolicy
from exhaust_plume.validation import (
  FPA_CLAIM_CEILING,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  DetectorResponse,
  FpaCameraOptics,
  FpaDigitizationPolicy,
  FpaDisplayLayer,
  FpaPixelGeometry,
  FpaSourceReference,
  FpaViewSelection,
  FpaVisualizationInput,
  FpaVisualizationSpec,
  digitize_expected_electrons,
  integrate_ray_transfer_to_fpa,
  project_fpa_view,
)


def _source() -> FpaSourceReference:
  return FpaSourceReference(
    capability_id='plume.optical.spectral-ray-transfer@1',
    schema_version='1.0.0',
    provider_id='provider-test',
    session_id='session-test',
    snapshot_id='snapshot-test',
    content_sha256='a' * 64,
    frame_id='sensor',
    source_status='OK',
    source_fidelity={'model_fidelity': 'PRESCRIBED'},
    source_applicability={'supported': True},
    source_provenance={'model_id': 'test'},
  )
####


def _inputs() -> FpaVisualizationInput:
  camera = FpaCameraOptics(
    camera_id='camera-test',
    focal_length_m=0.05,
    pixel_pitch_m=(5.0e-6, 6.0e-6),
    principal_point_px=(0.5, 0.5),
    aperture_area_m2=1.0e-4,
  )
  geometry = FpaPixelGeometry(
    width_px=2,
    height_px=2,
    ray_pixel_indices_row_col=((0, 0), (0, 1), (1, 0), (1, 1)),
    ray_collection_weights_m2_sr=(1.0e-6, 2.0e-6, 3.0e-6, 4.0e-6),
    camera_optics=camera,
  )
  detector = DetectorResponse(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    quantum_efficiency=(0.5, 0.6, 0.7),
    optical_throughput=(0.8, 0.9, 1.0),
    response_id='detector-test',
  )
  image = integrate_ray_transfer_to_fpa(
    detector.wavelengths_m,
    ((1.0, 2.0, 3.0),) * 4,
    geometry=geometry,
    detector=detector,
    exposure_s=2.0,
  )
  policy = FpaDigitizationPolicy(
    electrons_per_count=1.0e10,
    bit_depth=12,
    policy_id='adc-test',
  )
  digitized = digitize_expected_electrons(image, policy=policy)
  return FpaVisualizationInput(
    image=image,
    source=_source(),
    detector_response=detector,
    digitized=digitized,
    digitization_policy=policy,
    camera_optics=camera,
  )
####


def test_fpa_projection_preserves_source_identity_and_declared_pixel_coordinates() -> None:
  inputs = _inputs()
  spec = FpaVisualizationSpec.for_source(
    inputs.source,
    view_kind='fpa.pixel-inspector',
    selection=FpaViewSelection(row_index=1, column_index=0, wavelength_index=2),
  )
  projection = project_fpa_view(inputs, spec)

  assert projection.schema == 'plume.visualization.fpa-view@1'
  assert projection.source.content_sha256 == 'a' * 64
  assert projection.operator_ids == (
    FPA_PIXEL_DETECTOR_OPERATOR_ID,
    'op.sensor.fpa-digitization',
  )
  assert projection.selected_pixel.row_index == 1
  assert projection.selected_pixel.column_index == 0
  assert projection.selected_pixel.image_plane_xy_m == pytest.approx((-2.5e-6, 3.0e-6))
  assert projection.selected_wavelength_m == 3.0e-6
  assert projection.claim_ceiling == FPA_CLAIM_CEILING
  assert projection.model_dump()['source']['content_sha256'] == 'a' * 64


def test_fpa_projection_supports_counts_and_detector_response_views() -> None:
  inputs = _inputs()
  counts = project_fpa_view(
    inputs,
    FpaVisualizationSpec.for_source(
      inputs.source,
      view_kind='fpa.counts',
      display_layer=FpaDisplayLayer.DIGITIZED_COUNTS,
    ),
  )
  response = project_fpa_view(
    inputs,
    FpaVisualizationSpec.for_source(
      inputs.source,
      view_kind='fpa.detector-response',
      display_layer=FpaDisplayLayer.DETECTOR_RESPONSE,
    ),
  )

  assert counts.layer_values[0][0] == float(inputs.digitized.counts[0][0])
  assert response.detector_wavelengths_m == inputs.detector_response.wavelengths_m
  assert response.electron_response_per_joule == inputs.detector_response.electron_response_per_joule


def test_fpa_projection_rejects_unbound_specs_and_missing_deterministic_layers() -> None:
  inputs = _inputs()
  other_source = inputs.source.model_copy(update={'content_sha256': 'b' * 64})
  with pytest.raises(ValueError, match='different source result'):
    project_fpa_view(
      inputs,
      FpaVisualizationSpec.for_source(other_source, view_kind='fpa.overview'),
    )

  no_counts = FpaVisualizationInput(
    image=inputs.image,
    source=inputs.source,
    detector_response=inputs.detector_response,
    camera_optics=inputs.camera_optics,
  )
  with pytest.raises(ValueError, match='digitized output'):
    project_fpa_view(
      no_counts,
      FpaVisualizationSpec.for_source(
        inputs.source,
        view_kind='fpa.counts',
        display_layer=FpaDisplayLayer.DIGITIZED_COUNTS,
      ),
    )


def test_fpa_projection_rejects_invalid_pixels_when_policy_is_reject() -> None:
  inputs = _inputs()
  invalid_inputs = FpaVisualizationInput(
    image=replace(inputs.image, validity_mask=((True, False), (True, True))),
    source=inputs.source,
    detector_response=inputs.detector_response,
    camera_optics=inputs.camera_optics,
  )
  with pytest.raises(ValueError, match='invalid pixels'):
    project_fpa_view(
      invalid_inputs,
      FpaVisualizationSpec.for_source(
        invalid_inputs.source,
        view_kind='fpa.overview',
        invalid_sample_policy=InvalidSamplePolicy.REJECT,
      ),
    )
