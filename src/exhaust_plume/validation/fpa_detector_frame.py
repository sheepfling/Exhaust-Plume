"""Adapters from source-bound FPA operator outputs to the versioned frame contract."""

from __future__ import annotations

from math import isfinite

from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.contracts.fpa_detector_v1 import (
  FPA_DIGITIZATION_OPERATOR_ID,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  FPA_POINT_SPREAD_OPERATOR_ID,
  FPA_TEMPORAL_EXPOSURE_OPERATOR_ID,
  fpa_measurement_operator_digest,
  FpaCameraOpticsContract,
  FpaDetectorFrameResult,
  FpaDetectorResponseContract,
  FpaDetectorSourceReference,
  FpaDigitizationPolicyContract,
  FpaPointSpreadFunctionContract,
)
from exhaust_plume.validation.fpa_operators import FpaPixelGeometry
from exhaust_plume.validation.fpa_visualization import FpaVisualizationInput


def _source_times_s(inputs: FpaVisualizationInput) -> tuple[float, ...]:
  source = inputs.source
  raw_times = source.source_provenance.get('sample_times_s')
  if isinstance(raw_times, (tuple, list)) and raw_times:
    if any(isinstance(value, bool) for value in raw_times):
      raise ValueError('source exposure times must be numeric, not boolean')
    try:
      times = tuple(float(value) for value in raw_times)
    except (TypeError, ValueError) as error:
      raise ValueError('source exposure times must be numeric') from error
    ####
    if not all(isfinite(value) for value in times):
      raise ValueError('source exposure times must be finite')
    ####
    return times
  ####
  if source.source_time_s is not None:
    return (source.source_time_s,)
  ####
  provenance_time = source.source_provenance.get('time_s')
  if isinstance(provenance_time, bool):
    raise ValueError('source time must be numeric, not boolean')
  ####
  if provenance_time is not None:
    time_s = float(provenance_time)
    if isfinite(time_s):
      return (time_s,)
    ####
  ####
  raise ValueError('FPA detector frames require exact source or exposure times')
####


def to_fpa_detector_frame(
    inputs: FpaVisualizationInput,
    *,
    geometry: FpaPixelGeometry,
) -> FpaDetectorFrameResult:
  """Create a detector-frame result bound to the exact source and operator inputs.

  The geometry, detector response, and operation-input digest are required so
  the serialized detector image cannot be detached from the mapping and
  detector settings that produced it. This contract remains downstream of the
  ray-transfer capability and is not the spectral-radiance image capability.
  """

  if not isinstance(inputs, FpaVisualizationInput):
    raise TypeError('inputs must be FpaVisualizationInput')
  ####
  if not isinstance(geometry, FpaPixelGeometry):
    raise TypeError('geometry must be FpaPixelGeometry')
  ####
  image = inputs.image
  if image.operator_input_sha256 is None:
    raise ValueError('FPA frame requires an operator-bound input digest')
  ####
  if image.measurement_operator_sha256 is None:
    raise ValueError('FPA frame requires a measurement-operator digest')
  ####
  if image.source_binding != inputs.source.ray_source_binding:
    raise ValueError('FPA image must bind the exact ray-transfer source')
  ####
  if (image.width_px, image.height_px) != (geometry.width_px, geometry.height_px):
    raise ValueError('FPA image dimensions must match the exact pixel geometry')
  ####
  if image.camera_optics_id != geometry.camera_optics_id:
    raise ValueError('FPA image camera identity must match the pixel geometry')
  ####
  if image.camera_mapping_model_id != geometry.camera_mapping_model_id:
    raise ValueError('FPA image mapping identity must match the pixel geometry')
  ####
  geometry_digest = canonical_digest(geometry)
  if image.pixel_geometry_sha256 is None or image.pixel_geometry_sha256 != geometry_digest:
    raise ValueError('FPA image must bind the exact pixel geometry')
  ####
  detector = inputs.detector_response
  if detector is None:
    raise ValueError('FPA frame requires the detector response used by the operator')
  ####
  if detector.response_id != image.detector_response_id:
    raise ValueError('detector response identity must match the pixel image')
  ####
  geometry_camera = geometry.camera_optics
  if inputs.camera_optics is not None and inputs.camera_optics != geometry_camera:
    raise ValueError('visualization camera metadata must match the pixel geometry')
  ####
  geometry_psf = None if geometry_camera is None else geometry_camera.point_spread_function
  if geometry_psf is None:
    if any(value is not None for value in (
        image.point_spread_operator_id,
        image.point_spread_function_id,
        image.point_spread_function_sha256,
    )):
      raise ValueError('FPA image PSF metadata must match the exact pixel geometry')
    ####
  elif (
      image.point_spread_operator_id != FPA_POINT_SPREAD_OPERATOR_ID
      or image.point_spread_function_id != geometry_psf.model_id
      or image.point_spread_function_sha256 != geometry_psf.digest_sha256
  ):
    raise ValueError('FPA image PSF metadata must match the exact pixel geometry')
  ####
  if image.camera_optics_id is not None and geometry_camera is None:
    raise ValueError('camera optics metadata is required for this FPA image')
  ####
  source_times = _source_times_s(inputs)
  temporal_operator_id = (
    FPA_TEMPORAL_EXPOSURE_OPERATOR_ID
    if FPA_TEMPORAL_EXPOSURE_OPERATOR_ID in inputs.source.operator_chain
    else None
  )
  expected_measurement_operator_sha256 = fpa_measurement_operator_digest(
    pixel_operator_id=FPA_PIXEL_DETECTOR_OPERATOR_ID,
    temporal_operator_id=temporal_operator_id,
    pixel_geometry_sha256=geometry_digest,
    wavelengths_m=image.wavelengths_m,
    exposure_s=image.exposure_s,
    detector_response=inputs.detector_response,
    source_times_s=source_times if temporal_operator_id is not None else (),
  )
  if image.measurement_operator_sha256 != expected_measurement_operator_sha256:
    raise ValueError(
      'FPA image measurement-operator digest must match exact geometry, detector, exposure, and time inputs'
    )
  ####
  digitized = inputs.digitized
  policy = inputs.digitization_policy
  if (digitized is None) != (policy is None):
    raise ValueError('digitized counts and their policy must be supplied together')
  ####
  digitization_input_sha256 = None
  if digitized is not None and policy is not None:
    digitization_input_sha256 = canonical_digest({
      'operator_id': FPA_DIGITIZATION_OPERATOR_ID,
      'pixel_operator_input_sha256': image.operator_input_sha256,
      'expected_electrons_e': image.expected_electrons,
      'validity_mask': image.validity_mask,
      'digitization_policy': policy,
    })
  ####
  camera_contract = None
  if geometry_camera is not None:
    psf_contract = (
      None
      if geometry_psf is None
      else FpaPointSpreadFunctionContract(
        model_id=geometry_psf.model_id,
        kernel_weights=geometry_psf.kernel_weights,
        spectral_scope=geometry_psf.spectral_scope,
        edge_policy=geometry_psf.edge_policy,
        digest_sha256=geometry_psf.digest_sha256,
      )
    )
    camera_contract = FpaCameraOpticsContract(
      camera_id=geometry_camera.camera_id,
      focal_length_m=geometry_camera.focal_length_m,
      pixel_pitch_m=geometry_camera.pixel_pitch_m,
      principal_point_px=geometry_camera.principal_point_px,
      aperture_area_m2=geometry_camera.aperture_area_m2,
      mapping_model_id=geometry_camera.mapping_model_id,
      angular_projection_model_id=geometry_camera.angular_projection_model_id,
      on_axis_pixel_ifov_rad=geometry_camera.on_axis_pixel_ifov_rad,
      field_of_view_rad=geometry_camera.field_of_view_rad(
        width_px=image.width_px,
        height_px=image.height_px,
      ),
      point_spread_function=psf_contract,
    )
  ####
  digitization_contract = None
  if policy is not None:
    digitization_contract = FpaDigitizationPolicyContract(
      policy_id=policy.policy_id,
      electrons_per_count=policy.electrons_per_count,
      offset_counts=policy.offset_counts,
      bit_depth=policy.bit_depth,
      rounding_mode='nearest_even',
      saturation_mode='clip',
      invalid_count=policy.invalid_count,
    )
  ####
  return FpaDetectorFrameResult(
    source=FpaDetectorSourceReference(**inputs.source.model_dump(mode='python')),
    source_times_s=source_times,
    pixel_operator_id=FPA_PIXEL_DETECTOR_OPERATOR_ID,
    temporal_integration_operator_id=(
      FPA_TEMPORAL_EXPOSURE_OPERATOR_ID
      if FPA_TEMPORAL_EXPOSURE_OPERATOR_ID in inputs.source.operator_chain
      else None
    ),
    digitization_operator_id=(
      None if digitized is None else FPA_DIGITIZATION_OPERATOR_ID
    ),
    operator_input_sha256=image.operator_input_sha256,
    digitization_input_sha256=digitization_input_sha256,
    pixel_geometry_sha256=geometry_digest,
    measurement_operator_sha256=image.measurement_operator_sha256,
    width_px=image.width_px,
    height_px=image.height_px,
    exposure_s=image.exposure_s,
    wavelengths_m=image.wavelengths_m,
    expected_electrons_e=image.expected_electrons,
    dark_electrons_e=image.dark_electrons,
    noise_variance_e2=image.noise_variance_e2,
    validity_mask=image.validity_mask,
    detector=FpaDetectorResponseContract(
      response_id=detector.response_id,
      wavelengths_m=detector.wavelengths_m,
      quantum_efficiency=detector.quantum_efficiency,
      optical_throughput=detector.optical_throughput,
      dark_current_e_per_s=detector.dark_current_e_per_s,
      read_noise_std_e=detector.read_noise_std_e,
    ),
    camera_optics_id=image.camera_optics_id,
    camera_mapping_model_id=image.camera_mapping_model_id,
    camera_optics=camera_contract,
    point_spread_operator_id=image.point_spread_operator_id,
    digitization_policy=digitization_contract,
    digitized_counts=None if digitized is None else digitized.counts,
    digitized_validity_mask=None if digitized is None else digitized.validity_mask,
    saturated_mask=None if digitized is None else digitized.saturated_mask,
    source_semantics=image.source_semantics,
    atmospheric_path_operator_id=image.atmospheric_path_operator_id,
    atmospheric_path_layer_digest=image.atmospheric_path_layer_digest,
    atmospheric_path_layer_ids=image.atmospheric_path_layer_ids,
    validation_status=inputs.validation_status,
  )
####


__all__ = ('to_fpa_detector_frame',)
