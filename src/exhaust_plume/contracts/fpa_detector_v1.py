"""Versioned downstream detector-frame contract, independent of plume radiance."""

from __future__ import annotations

from math import atan, fsum, isclose, isfinite
from typing import Any, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  MatrixBool,
  MatrixFloat,
  canonical_digest,
  validate_rectangular_matrix,
)

FPA_DETECTOR_FRAME_SCHEMA = 'plume.fpa.detector-frame@1'
FPA_PIXEL_DETECTOR_OPERATOR_ID = 'op.sensor.fpa-pixel-detector'
FPA_POINT_SPREAD_OPERATOR_ID = 'op.sensor.fpa-point-spread'
FPA_DIGITIZATION_OPERATOR_ID = 'op.sensor.fpa-digitization'
FPA_TEMPORAL_EXPOSURE_OPERATOR_ID = 'op.sensor.fpa-temporal-exposure-integral'
FPA_PINHOLE_RECTILINEAR_PROJECTION_MODEL_ID = 'pinhole-rectilinear-v1'
FPA_DETECTOR_FRAME_CLAIM_CEILING = (
  'Expected detector electrons and deterministic ADC expectations only; '
  'not measured images, noise realizations, or detection claims.'
)


def _contains_boolean_numeric(value: Any) -> bool:
  if isinstance(value, bool):
    return True
  ####
  if isinstance(value, (tuple, list)):
    return any(_contains_boolean_numeric(item) for item in value)
  ####
  return False
####


def _reject_boolean_numeric_fields(
    values: Any,
    field_names: tuple[str, ...],
) -> Any:
  if not isinstance(values, Mapping):
    return values
  ####
  for field_name in field_names:
    if field_name in values and _contains_boolean_numeric(values[field_name]):
      raise ValueError(f'{field_name} must be numeric, not booleans')
    ####
  ####
  return values
####


def fpa_measurement_operator_digest(
  *,
  pixel_operator_id: str,
  temporal_operator_id: str | None,
  pixel_geometry_sha256: str,
  wavelengths_m: tuple[float, ...],
  exposure_s: float,
  detector_response: Any,
  source_times_s: tuple[float, ...] = (),
) -> str:
  """Digest camera, detector, exposure, and optional temporal sampling inputs."""

  return canonical_digest({
    'pixel_operator_id': pixel_operator_id,
    'temporal_operator_id': temporal_operator_id,
    'pixel_geometry_sha256': pixel_geometry_sha256,
    'wavelengths_m': wavelengths_m,
    'exposure_s': exposure_s,
    'detector_response': detector_response,
    'source_times_s': source_times_s,
  })


class FpaDetectorSourceReference(ApiModel):
  """Exact ray-result identity and source metadata consumed by the detector."""

  source_kind: Literal['ray-transfer'] = 'ray-transfer'
  capability_id: Literal['plume.optical.spectral-ray-transfer@1']
  schema_version: str = Field(min_length=1)
  provider_id: str = Field(min_length=1)
  session_id: str = Field(min_length=1)
  snapshot_id: str = Field(min_length=1)
  source_time_s: float | None = None
  content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  frame_id: str = Field(min_length=1)
  source_status: str = Field(min_length=1)
  source_fidelity: Mapping[str, Any] = Field(default_factory=dict)
  source_applicability: Mapping[str, Any] = Field(default_factory=dict)
  source_provenance: Mapping[str, Any] = Field(default_factory=dict)
  operator_chain: tuple[str, ...] = Field(min_length=1)

  @field_validator('source_time_s', mode='before')
  @classmethod
  def reject_boolean_source_time(cls, value: Any) -> Any:
    return _reject_boolean_numeric_fields({'source_time_s': value}, ('source_time_s',))['source_time_s']
  ####

  @model_validator(mode='after')
  def validate_source(self) -> 'FpaDetectorSourceReference':
    if self.source_time_s is not None and not isfinite(self.source_time_s):
      raise ValueError('source_time_s must be finite when supplied')
    ####
    for time_field in ('sample_times_s', 'time_s'):
      if _contains_boolean_numeric(self.source_provenance.get(time_field)):
        raise ValueError(f'source_provenance.{time_field} must contain numeric times, not booleans')
      ####
    ####
    if not self.operator_chain or self.operator_chain[0] != FPA_PIXEL_DETECTOR_OPERATOR_ID:
      raise ValueError('operator_chain must begin with the FPA pixel detector operator')
    ####
    return self
  ####
####


class FpaDetectorResponseContract(ApiModel):
  """Spectral detector response and deterministic noise parameters."""

  response_id: str = Field(min_length=1)
  wavelengths_m: tuple[float, ...] = Field(min_length=2)
  quantum_efficiency: tuple[float, ...] = Field(min_length=2)
  optical_throughput: tuple[float, ...] = Field(min_length=2)
  dark_current_e_per_s: float = Field(ge=0.0)
  read_noise_std_e: float = Field(ge=0.0)

  @model_validator(mode='before')
  @classmethod
  def reject_boolean_numeric_inputs(cls, values: Any) -> Any:
    return _reject_boolean_numeric_fields(
      values,
      (
        'wavelengths_m',
        'quantum_efficiency',
        'optical_throughput',
        'dark_current_e_per_s',
        'read_noise_std_e',
      ),
    )
  ####

  @model_validator(mode='after')
  def validate_response(self) -> 'FpaDetectorResponseContract':
    if not all(isfinite(value) and value > 0.0 for value in self.wavelengths_m):
      raise ValueError('detector wavelengths must be finite and positive')
    ####
    if any(right <= left for left, right in zip(self.wavelengths_m, self.wavelengths_m[1:])):
      raise ValueError('detector wavelengths must be strictly increasing')
    ####
    if not (
        len(self.wavelengths_m)
        == len(self.quantum_efficiency)
        == len(self.optical_throughput)
    ):
      raise ValueError('detector response vectors must match the wavelength axis')
    ####
    if any(
        not isfinite(value) or value < 0.0 or value > 1.0
        for value in (*self.quantum_efficiency, *self.optical_throughput)
    ):
      raise ValueError('quantum efficiency and throughput must lie in [0, 1]')
    ####
    if not (isfinite(self.dark_current_e_per_s) and isfinite(self.read_noise_std_e)):
      raise ValueError('detector noise parameters must be finite')
    ####
    return self
  ####
####


class FpaPointSpreadFunctionContract(ApiModel):
  """Exact achromatic PSF stencil and finite-sensor validity policy."""

  model_id: str = Field(min_length=1)
  kernel_weights: MatrixFloat
  spectral_scope: Literal['achromatic']
  edge_policy: Literal['mask-incomplete-support']
  digest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

  @field_validator('model_id', mode='before')
  @classmethod
  def normalize_model_id(cls, value: Any) -> Any:
    if isinstance(value, str):
      return value.strip()
    ####
    return value
  ####

  @field_validator('kernel_weights', mode='before')
  @classmethod
  def reject_boolean_weights(cls, value: Any) -> Any:
    _reject_boolean_numeric_fields(
      {'kernel_weights': value},
      ('kernel_weights',),
    )
    return value
  ####

  @model_validator(mode='after')
  def validate_psf(self) -> 'FpaPointSpreadFunctionContract':
    if not self.kernel_weights or not self.kernel_weights[0]:
      raise ValueError('PSF kernel must be a nonempty rectangular matrix')
    ####
    width = len(self.kernel_weights[0])
    if len(self.kernel_weights) % 2 != 1 or width % 2 != 1:
      raise ValueError('PSF kernel dimensions must be odd')
    ####
    if any(len(row) != width for row in self.kernel_weights):
      raise ValueError('PSF kernel must be rectangular')
    ####
    if any(
        not isfinite(value) or value < 0.0
        for row in self.kernel_weights
        for value in row
    ):
      raise ValueError('PSF kernel weights must be finite and nonnegative')
    ####
    if not isclose(
        fsum(value for row in self.kernel_weights for value in row),
        1.0,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
      raise ValueError('PSF kernel weights must sum to one within 1e-12')
    ####
    expected_digest = canonical_digest({
      'model_id': self.model_id,
      'kernel_weights': self.kernel_weights,
      'spectral_scope': self.spectral_scope,
      'edge_policy': self.edge_policy,
    })
    if self.digest_sha256 != expected_digest:
      raise ValueError('PSF digest must match its exact kernel, scope, and edge policy')
    ####
    return self
  ####
####


class FpaCameraOpticsContract(ApiModel):
  """Camera metadata attached to the ray-to-pixel mapping."""

  camera_id: str = Field(min_length=1)
  focal_length_m: float = Field(gt=0.0)
  pixel_pitch_m: tuple[float, float]
  principal_point_px: tuple[float, float]
  aperture_area_m2: float = Field(gt=0.0)
  mapping_model_id: str = Field(min_length=1)
  angular_projection_model_id: Literal[
    'pinhole-rectilinear-v1'
  ] | None = None
  on_axis_pixel_ifov_rad: tuple[float, float] | None = Field(
    default=None,
    description='On-axis horizontal and vertical pixel IFOV in camera-local radians.',
  )
  field_of_view_rad: tuple[float, float] | None = Field(
    default=None,
    description='Horizontal and vertical sensor FOV in camera-local radians.',
  )
  point_spread_function: FpaPointSpreadFunctionContract | None = None

  @model_validator(mode='before')
  @classmethod
  def reject_boolean_numeric_inputs(cls, values: Any) -> Any:
    return _reject_boolean_numeric_fields(
      values,
      (
        'focal_length_m',
        'pixel_pitch_m',
        'principal_point_px',
        'aperture_area_m2',
        'on_axis_pixel_ifov_rad',
        'field_of_view_rad',
      ),
    )
  ####

  @model_validator(mode='after')
  def validate_camera(self) -> 'FpaCameraOpticsContract':
    values = (
      self.focal_length_m,
      *self.pixel_pitch_m,
      *self.principal_point_px,
      self.aperture_area_m2,
    )
    if not all(isfinite(value) for value in values):
      raise ValueError('camera geometry must contain finite values')
    ####
    if any(value <= 0.0 for value in (*self.pixel_pitch_m, self.aperture_area_m2)):
      raise ValueError('pixel pitch and aperture area must be positive')
    ####
    angular_values = (self.on_axis_pixel_ifov_rad, self.field_of_view_rad)
    if self.angular_projection_model_id is None:
      if any(value is not None for value in angular_values):
        raise ValueError('angular IFOV/FOV values require a projection model identity')
    else:
      if any(value is None for value in angular_values):
        raise ValueError('declared projection model requires IFOV and FOV values')
      ####
      assert self.on_axis_pixel_ifov_rad is not None
      assert self.field_of_view_rad is not None
      for name, pair in (
          ('on_axis_pixel_ifov_rad', self.on_axis_pixel_ifov_rad),
          ('field_of_view_rad', self.field_of_view_rad),
      ):
        if len(pair) != 2 or not all(
            isfinite(value) and 0.0 < value < 3.141592653589793
            for value in pair
        ):
          raise ValueError(f'{name} must contain two finite angles in (0, pi)')
        ####
      ####
    ####
    return self
  ####
####


class FpaDigitizationPolicyContract(ApiModel):
  """Deterministic expected-electron-to-ADC-count transfer settings."""

  policy_id: str = Field(min_length=1)
  electrons_per_count: float = Field(gt=0.0)
  offset_counts: float
  bit_depth: int = Field(ge=1, le=32)
  rounding_mode: Literal['nearest_even']
  saturation_mode: Literal['clip']
  invalid_count: int = Field(ge=0)

  @model_validator(mode='before')
  @classmethod
  def reject_boolean_numeric_inputs(cls, values: Any) -> Any:
    return _reject_boolean_numeric_fields(
      values,
      ('electrons_per_count', 'offset_counts', 'bit_depth', 'invalid_count'),
    )
  ####

  @model_validator(mode='after')
  def validate_policy(self) -> 'FpaDigitizationPolicyContract':
    if not (isfinite(self.electrons_per_count) and isfinite(self.offset_counts)):
      raise ValueError('digitization scale and offset must be finite')
    ####
    if self.invalid_count > (1 << self.bit_depth) - 1:
      raise ValueError('invalid_count must lie inside the ADC range')
    ####
    return self
  ####
####


class FpaDetectorFrameResult(ApiModel):
  """Source-bound detector result with explicit units, masks, and pixel lineage.

  ``expected_electrons_e`` is the expected total signal plus dark electrons.
  ``dark_electrons_e`` is the dark-current component, and
  ``noise_variance_e2`` is the expected variance including shot and read noise.
  None of these fields represents a sampled measurement.
  """

  schema_id: Literal['plume.fpa.detector-frame@1'] = FPA_DETECTOR_FRAME_SCHEMA
  source: FpaDetectorSourceReference
  source_times_s: tuple[float, ...] = Field(min_length=1)
  pixel_operator_id: Literal['op.sensor.fpa-pixel-detector'] = FPA_PIXEL_DETECTOR_OPERATOR_ID
  temporal_integration_operator_id: Literal[
    'op.sensor.fpa-temporal-exposure-integral'
  ] | None = None
  digitization_operator_id: Literal['op.sensor.fpa-digitization'] | None = None
  operator_input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  digitization_input_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
  pixel_geometry_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  measurement_operator_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  width_px: int = Field(gt=0)
  height_px: int = Field(gt=0)
  pixel_indexing: Literal['zero-based-row-column'] = 'zero-based-row-column'
  exposure_s: float = Field(gt=0.0)
  wavelengths_m: tuple[float, ...] = Field(min_length=2)
  expected_electrons_e: MatrixFloat = Field(
    description='Expected total signal plus dark electrons per pixel, in electrons.'
  )
  dark_electrons_e: MatrixFloat = Field(
    description='Dark-current contribution per pixel, in electrons.'
  )
  noise_variance_e2: MatrixFloat = Field(
    description='Expected shot plus read-noise variance per pixel, in electrons squared.'
  )
  validity_mask: MatrixBool
  detector: FpaDetectorResponseContract
  camera_optics_id: str | None = None
  camera_mapping_model_id: str | None = None
  camera_optics: FpaCameraOpticsContract | None = None
  point_spread_operator_id: Literal['op.sensor.fpa-point-spread'] | None = None
  digitization_policy: FpaDigitizationPolicyContract | None = None
  digitized_counts: tuple[tuple[int, ...], ...] | None = None
  digitized_validity_mask: MatrixBool | None = None
  saturated_mask: MatrixBool | None = None
  source_semantics: str = Field(min_length=1)
  atmospheric_path_operator_id: str | None = None
  atmospheric_path_layer_digest: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
  atmospheric_path_layer_ids: tuple[str, ...] = ()
  claim_ceiling: Literal[
    'Expected detector electrons and deterministic ADC expectations only; '
    'not measured images, noise realizations, or detection claims.'
  ] = FPA_DETECTOR_FRAME_CLAIM_CEILING
  validation_status: str = Field(
    default='deterministic-operator-output; external-detector-validation-open',
    min_length=1,
  )

  @model_validator(mode='before')
  @classmethod
  def reject_boolean_numeric_inputs(cls, values: Any) -> Any:
    return _reject_boolean_numeric_fields(
      values,
      (
        'source_times_s',
        'width_px',
        'height_px',
        'exposure_s',
        'wavelengths_m',
        'expected_electrons_e',
        'dark_electrons_e',
        'noise_variance_e2',
        'digitized_counts',
      ),
    )
  ####

  @model_validator(mode='after')
  def validate_frame(self) -> 'FpaDetectorFrameResult':
    if not all(isfinite(time_s) for time_s in self.source_times_s):
      raise ValueError('source_times_s must contain only finite values')
    ####
    if any(right <= left for left, right in zip(self.source_times_s, self.source_times_s[1:])):
      raise ValueError('source_times_s must be strictly increasing')
    ####
    temporal = FPA_TEMPORAL_EXPOSURE_OPERATOR_ID in self.source.operator_chain
    if temporal:
      if len(self.source_times_s) < 2:
        raise ValueError('a temporal exposure requires at least two source times')
      ####
      if self.temporal_integration_operator_id != FPA_TEMPORAL_EXPOSURE_OPERATOR_ID:
        raise ValueError('temporal operator identity must match the source lineage')
      ####
      if not isclose(
          self.source_times_s[-1] - self.source_times_s[0],
          self.exposure_s,
          rel_tol=1.0e-12,
          abs_tol=1.0e-12,
      ):
        raise ValueError('temporal exposure duration must match the sampled time span')
      ####
    else:
      if len(self.source_times_s) != 1:
        raise ValueError('multiple source times require the temporal exposure operator')
      ####
      if self.temporal_integration_operator_id is not None:
        raise ValueError('temporal operator identity requires temporal source lineage')
      ####
    ####
    if self.source.source_time_s is not None and len(self.source_times_s) == 1:
      if self.source_times_s[0] != self.source.source_time_s:
        raise ValueError('source time must match the exact ray-result snapshot')
      ####
    ####
    provenance_times = self.source.source_provenance.get('sample_times_s')
    if provenance_times is not None and tuple(provenance_times) != self.source_times_s:
      raise ValueError('source times must match the retained exposure provenance')
    ####
    if not all(isfinite(value) and value > 0.0 for value in self.wavelengths_m):
      raise ValueError('frame wavelengths must be finite and positive')
    ####
    if any(right <= left for left, right in zip(self.wavelengths_m, self.wavelengths_m[1:])):
      raise ValueError('frame wavelengths must be strictly increasing')
    ####
    if (
        self.detector.wavelengths_m[0] > self.wavelengths_m[0]
        or self.detector.wavelengths_m[-1] < self.wavelengths_m[-1]
    ):
      raise ValueError('detector response must cover the frame wavelength axis')
    ####
    expected_measurement_operator_digest = fpa_measurement_operator_digest(
      pixel_operator_id=self.pixel_operator_id,
      temporal_operator_id=self.temporal_integration_operator_id,
      pixel_geometry_sha256=self.pixel_geometry_sha256,
      wavelengths_m=self.wavelengths_m,
      exposure_s=self.exposure_s,
      detector_response=self.detector,
      source_times_s=self.source_times_s if temporal else (),
    )
    if self.measurement_operator_sha256 != expected_measurement_operator_digest:
      raise ValueError(
        'measurement operator digest must match geometry, detector, exposure, and time inputs'
      )
    ####
    shape = (self.height_px, self.width_px)
    for name, matrix in (
      ('expected_electrons_e', self.expected_electrons_e),
      ('dark_electrons_e', self.dark_electrons_e),
      ('noise_variance_e2', self.noise_variance_e2),
      ('validity_mask', self.validity_mask),
    ):
      if validate_rectangular_matrix(matrix, name) != shape:
        raise ValueError(f'{name} must have shape {shape}')
      ####
    ####
    numeric_matrices = (
      self.expected_electrons_e,
      self.dark_electrons_e,
      self.noise_variance_e2,
    )
    if any(
        not isfinite(value) or value < 0.0
        for matrix in numeric_matrices
        for row in matrix
        for value in row
    ):
      raise ValueError('detector layers must contain finite nonnegative values')
    ####
    read_variance = self.detector.read_noise_std_e ** 2
    dark_rate = self.detector.dark_current_e_per_s
    for row in range(self.height_px):
      for column in range(self.width_px):
        total = self.expected_electrons_e[row][column]
        dark = self.dark_electrons_e[row][column]
        variance = self.noise_variance_e2[row][column]
        if not self.validity_mask[row][column]:
          if total != 0.0 or dark != 0.0 or variance != 0.0:
            raise ValueError('invalid pixels must have zero numeric detector layers')
          ####
          continue
        ####
        if dark > total and not isclose(dark, total, rel_tol=1.0e-12, abs_tol=1.0e-12):
          raise ValueError('dark electrons cannot exceed total expected electrons')
        ####
        if not isclose(dark, dark_rate * self.exposure_s, rel_tol=1.0e-10, abs_tol=1.0e-10):
          raise ValueError('dark-electron layer must match detector dark current and exposure')
        ####
        if not isclose(total + read_variance, variance, rel_tol=1.0e-10, abs_tol=1.0e-10):
          raise ValueError('noise variance must equal expected electrons plus read-noise variance')
        ####
      ####
    ####
    camera_ids = (self.camera_optics_id, self.camera_mapping_model_id)
    if self.camera_optics is not None:
      if camera_ids != (self.camera_optics.camera_id, self.camera_optics.mapping_model_id):
        raise ValueError('camera metadata must match the declared camera identifiers')
      ####
      camera = self.camera_optics
      if camera.point_spread_function is None:
        if self.point_spread_operator_id is not None:
          raise ValueError('point-spread operator identity requires camera PSF metadata')
      elif self.point_spread_operator_id != FPA_POINT_SPREAD_OPERATOR_ID:
        raise ValueError('camera PSF metadata requires its point-spread operator identity')
      ####
      if camera.angular_projection_model_id is not None:
        pitch_x, pitch_y = camera.pixel_pitch_m
        principal_x, principal_y = camera.principal_point_px
        focal_length = camera.focal_length_m
        expected_ifov = (
          2.0 * atan(pitch_x / (2.0 * focal_length)),
          2.0 * atan(pitch_y / (2.0 * focal_length)),
        )
        expected_fov = (
          atan(((self.width_px - 0.5 - principal_x) * pitch_x) / focal_length)
          - atan(((-0.5 - principal_x) * pitch_x) / focal_length),
          atan(((self.height_px - 0.5 - principal_y) * pitch_y) / focal_length)
          - atan(((-0.5 - principal_y) * pitch_y) / focal_length),
        )
        assert camera.on_axis_pixel_ifov_rad is not None
        assert camera.field_of_view_rad is not None
        for name, actual, expected in (
            ('IFOV', camera.on_axis_pixel_ifov_rad, expected_ifov),
            ('FOV', camera.field_of_view_rad, expected_fov),
        ):
          if any(
              not isclose(value, target, rel_tol=1.0e-12, abs_tol=1.0e-15)
              for value, target in zip(actual, expected, strict=True)
          ):
            raise ValueError(f'camera {name} values must match its pinhole geometry')
          ####
        ####
      ####
    elif any(value is not None for value in camera_ids):
      raise ValueError('camera metadata is required when camera identifiers are declared')
    elif self.point_spread_operator_id is not None:
      raise ValueError('point-spread operator identity requires camera PSF metadata')
    ####
    digitized_layers = (
      self.digitized_counts,
      self.digitized_validity_mask,
      self.saturated_mask,
    )
    if any(layer is not None for layer in digitized_layers):
      if any(layer is None for layer in digitized_layers) or self.digitization_policy is None:
        raise ValueError('digitized counts require policy, validity, and saturation layers')
      ####
      if self.digitization_operator_id != FPA_DIGITIZATION_OPERATOR_ID:
        raise ValueError('digitized counts require the deterministic ADC operator identity')
      ####
      if self.digitization_input_sha256 is None:
        raise ValueError('digitized counts require a digest of their exact input and policy')
      ####
      assert self.digitized_counts is not None
      assert self.digitized_validity_mask is not None
      assert self.saturated_mask is not None
      if validate_rectangular_matrix(self.digitized_counts, 'digitized_counts') != shape:
        raise ValueError(f'digitized_counts must have shape {shape}')
      ####
      for name, mask in (
        ('digitized_validity_mask', self.digitized_validity_mask),
        ('saturated_mask', self.saturated_mask),
      ):
        if validate_rectangular_matrix(mask, name) != shape:
          raise ValueError(f'{name} must have shape {shape}')
        ####
      ####
      full_scale = (1 << self.digitization_policy.bit_depth) - 1
      expected_digitization_digest = canonical_digest({
        'operator_id': FPA_DIGITIZATION_OPERATOR_ID,
        'pixel_operator_input_sha256': self.operator_input_sha256,
        'expected_electrons_e': self.expected_electrons_e,
        'validity_mask': self.validity_mask,
        'digitization_policy': self.digitization_policy,
      })
      if self.digitization_input_sha256 != expected_digitization_digest:
        raise ValueError('digitization input digest does not match the exact image and policy')
      ####
      for row in range(self.height_px):
        for column in range(self.width_px):
          count = self.digitized_counts[row][column]
          if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= full_scale:
            raise ValueError('digitized counts must be integers inside the ADC range')
          ####
          if self.digitized_validity_mask[row][column] != self.validity_mask[row][column]:
            raise ValueError('digitized and detector validity masks must match')
          ####
          if not self.validity_mask[row][column] and count != self.digitization_policy.invalid_count:
            raise ValueError('invalid pixels must use the declared invalid ADC count')
          ####
          if not self.validity_mask[row][column] and self.saturated_mask[row][column]:
            raise ValueError('invalid pixels cannot be marked saturated')
          ####
          if self.validity_mask[row][column]:
            unbounded_count = round(
              self.expected_electrons_e[row][column]
              / self.digitization_policy.electrons_per_count
              + self.digitization_policy.offset_counts
            )
            expected_count = min(max(unbounded_count, 0), full_scale)
            expected_saturation = unbounded_count < 0 or unbounded_count > full_scale
            if count != expected_count or self.saturated_mask[row][column] != expected_saturation:
              raise ValueError('ADC count and saturation layers do not match the declared policy')
            ####
          ####
          if self.saturated_mask[row][column] and count != full_scale:
            raise ValueError('saturated pixels must be clipped to ADC full scale')
          ####
        ####
      ####
    elif any((
      self.digitization_policy is not None,
      self.digitization_operator_id is not None,
      self.digitization_input_sha256 is not None,
    )):
      raise ValueError('digitization policy and lineage require digitized output layers')
    ####
    ####
    if self.atmospheric_path_operator_id is None:
      if self.atmospheric_path_layer_digest is not None or self.atmospheric_path_layer_ids:
        raise ValueError('atmospheric layer lineage requires an operator ID')
      ####
    elif self.atmospheric_path_layer_digest is None:
      raise ValueError('atmospheric path operator requires its layer digest')
    ####
    if any(not layer_id for layer_id in self.atmospheric_path_layer_ids):
      raise ValueError('atmospheric layer IDs must be nonempty')
    ####
    return self
  ####

  def content_digest_sha256(self) -> str:
    """Return the canonical digest of this complete detector-frame result."""

    return canonical_digest(self)
  ####
####


__all__ = (
  'FPA_DETECTOR_FRAME_CLAIM_CEILING',
  'fpa_measurement_operator_digest',
  'FPA_DETECTOR_FRAME_SCHEMA',
  'FPA_DIGITIZATION_OPERATOR_ID',
  'FPA_PIXEL_DETECTOR_OPERATOR_ID',
  'FPA_POINT_SPREAD_OPERATOR_ID',
  'FPA_TEMPORAL_EXPOSURE_OPERATOR_ID',
  'FpaCameraOpticsContract',
  'FpaDetectorFrameResult',
  'FpaDetectorResponseContract',
  'FpaDetectorSourceReference',
  'FpaDigitizationPolicyContract',
  'FpaPointSpreadFunctionContract',
)
