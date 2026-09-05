"""Deterministic downstream pixel/detector operators for ray-transfer results.

The adapter in this module is deliberately downstream of the optical product.
It converts source spectral radiance into expected detector electrons using
explicit ray collection weights, a detector response, and an exposure time.
It does not create a plume field, mutate the ray-transfer contract, sample
random noise, or advertise a focal-plane provider.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import fsum, isfinite

from exhaust_plume.validation.measurement_operators import sample_spectral_rows
from exhaust_plume.contracts.ray_transfer_v1 import SpectralRayTransferResult
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.validation.sensor_operators import (
  ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID,
  AtmosphericPathLayer,
  apply_atmospheric_path_layers,
  compose_atmospheric_path_layers,
)


FPA_PIXEL_DETECTOR_OPERATOR_ID = 'op.sensor.fpa-pixel-detector'
FPA_DIGITIZATION_OPERATOR_ID = 'op.sensor.fpa-digitization'
PLANCK_CONSTANT_J_S = 6.62607015e-34
SPEED_OF_LIGHT_M_PER_S = 299792458.0

FloatMatrix = tuple[tuple[float, ...], ...]
BoolMatrix = tuple[tuple[bool, ...], ...]


def _positive_axis(values: tuple[float, ...] | list[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if len(axis) < 2 or not all(isfinite(value) and value > 0.0 for value in axis):
    raise ValueError(f'{field_name} must contain at least two finite positive values')
  ####
  if any(right <= left for left, right in zip(axis, axis[1:])):
    raise ValueError(f'{field_name} must be strictly increasing')
  ####
  return axis
####


def _finite_vector(
    values: tuple[float, ...] | list[float],
    *,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> tuple[float, ...]:
  vector = tuple(float(value) for value in values)
  if not vector or any(not isfinite(value) for value in vector):
    raise ValueError(f'{field_name} must contain finite values')
  ####
  if minimum is not None and any(value < minimum for value in vector):
    raise ValueError(f'{field_name} must be >= {minimum:g}')
  ####
  if maximum is not None and any(value > maximum for value in vector):
    raise ValueError(f'{field_name} must be <= {maximum:g}')
  ####
  return vector
####


def _matrix(
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    *,
    row_count: int,
    column_count: int,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> FloatMatrix:
  matrix = tuple(tuple(float(value) for value in row) for row in values)
  if len(matrix) != row_count or any(len(row) != column_count for row in matrix):
    raise ValueError(f'{field_name} must have shape ({row_count}, {column_count})')
  ####
  if any(not isfinite(value) for row in matrix for value in row):
    raise ValueError(f'{field_name} must contain finite values')
  ####
  if minimum is not None and any(value < minimum for row in matrix for value in row):
    raise ValueError(f'{field_name} values must be >= {minimum:g}')
  ####
  if maximum is not None and any(value > maximum for row in matrix for value in row):
    raise ValueError(f'{field_name} values must be <= {maximum:g}')
  ####
  return matrix
####


def _bool_matrix(
  values: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]],
  *,
  row_count: int,
  column_count: int,
  field_name: str,
) -> BoolMatrix:
  matrix = tuple(tuple(value for value in row) for row in values)
  if len(matrix) != row_count or any(len(row) != column_count for row in matrix):
    raise ValueError(f'{field_name} must have shape ({row_count}, {column_count})')
  ####
  if any(not isinstance(value, bool) for row in matrix for value in row):
    raise ValueError(f'{field_name} must contain boolean values')
  ####
  return matrix
####


def _positive_dimension(value: int, field_name: str) -> int:
  if isinstance(value, bool) or not isinstance(value, int) or value < 1:
    raise ValueError(f'{field_name} must be a positive integer')
  ####
  return value
####


def _optional_identity(value: str | None, field_name: str) -> str | None:
  if value is not None and (not isinstance(value, str) or not value):
    raise ValueError(f'{field_name} must be a nonempty string when supplied')
  ####
  return value
####


@dataclass(frozen=True, slots=True)
class FpaCameraOptics:
  """Declared camera/optics metadata for a ray-to-pixel mapping.

  This record does not generate rays or infer a projection.  The caller must
  provide the explicit pixel indices and ``m² sr`` collection weights in
  :class:`FpaPixelGeometry`; this record preserves the camera/optics identity
  that was used to produce that mapping.
  """

  camera_id: str
  focal_length_m: float
  pixel_pitch_m: tuple[float, float]
  principal_point_px: tuple[float, float]
  aperture_area_m2: float
  mapping_model_id: str = 'declared-ray-to-pixel-mapping-v1'

  def __post_init__(self) -> None:
    if not self.camera_id:
      raise ValueError('camera_id must not be empty')
    ####
    if not isfinite(self.focal_length_m) or self.focal_length_m <= 0.0:
      raise ValueError('focal_length_m must be finite and positive')
    ####
    pixel_pitch = tuple(float(value) for value in self.pixel_pitch_m)
    if len(pixel_pitch) != 2 or not all(isfinite(value) and value > 0.0 for value in pixel_pitch):
      raise ValueError('pixel_pitch_m must contain two finite positive values')
    ####
    principal_point = tuple(float(value) for value in self.principal_point_px)
    if len(principal_point) != 2 or not all(isfinite(value) for value in principal_point):
      raise ValueError('principal_point_px must contain two finite values')
    ####
    if not isfinite(self.aperture_area_m2) or self.aperture_area_m2 <= 0.0:
      raise ValueError('aperture_area_m2 must be finite and positive')
    ####
    if not self.mapping_model_id:
      raise ValueError('mapping_model_id must not be empty')
    ####
    object.__setattr__(self, 'pixel_pitch_m', pixel_pitch)
    object.__setattr__(self, 'principal_point_px', principal_point)
  ####
####


@dataclass(frozen=True, slots=True)
class FpaPixelGeometry:
  """Mapping from requested rays to pixels and collection weights.

  ``ray_pixel_indices_row_col`` uses zero-based ``(row, column)`` indices.
  Each collection weight has units m² sr and represents the aperture-area
  times solid-angle quadrature weight assigned to that ray.
  """

  width_px: int
  height_px: int
  ray_pixel_indices_row_col: tuple[tuple[int, int], ...]
  ray_collection_weights_m2_sr: tuple[float, ...]
  camera_optics: FpaCameraOptics | None = None

  def __post_init__(self) -> None:
    width = _positive_dimension(self.width_px, 'width_px')
    height = _positive_dimension(self.height_px, 'height_px')
    normalized_indices: list[tuple[int, int]] = []
    for index, pair in enumerate(self.ray_pixel_indices_row_col):
      if len(pair) != 2:
        raise ValueError(f'ray_pixel_indices_row_col[{index}] must contain two indices')
      ####
      row, column = pair
      if (
          isinstance(row, bool)
          or not isinstance(row, int)
          or isinstance(column, bool)
          or not isinstance(column, int)
      ):
        raise ValueError('ray pixel indices must contain integers')
      ####
      normalized_indices.append((row, column))
    ####
    indices: tuple[tuple[int, int], ...] = tuple(normalized_indices)
    if not indices:
      raise ValueError('ray_pixel_indices_row_col must not be empty')
    ####
    if any(
        row < 0 or row >= height or column < 0 or column >= width
        for row, column in indices
    ):
      raise ValueError('ray pixel indices must lie inside the declared image grid')
    ####
    weights = _finite_vector(
      self.ray_collection_weights_m2_sr,
      field_name='ray_collection_weights_m2_sr',
      minimum=0.0,
    )
    if len(indices) != len(weights) or any(weight <= 0.0 for weight in weights):
      raise ValueError('each ray must have one strictly positive collection weight')
    ####
    if self.camera_optics is not None and not isinstance(self.camera_optics, FpaCameraOptics):
      raise ValueError('camera_optics must be FpaCameraOptics when supplied')
    ####
    object.__setattr__(self, 'width_px', width)
    object.__setattr__(self, 'height_px', height)
    object.__setattr__(self, 'ray_pixel_indices_row_col', indices)
    object.__setattr__(self, 'ray_collection_weights_m2_sr', weights)
  ####

  @property
  def camera_optics_id(self) -> str | None:
    return None if self.camera_optics is None else self.camera_optics.camera_id
  ####

  @property
  def camera_mapping_model_id(self) -> str | None:
    return None if self.camera_optics is None else self.camera_optics.mapping_model_id
  ####
####


@dataclass(frozen=True, slots=True)
class DetectorResponse:
  """Spectral detector response and explicit additive noise parameters.

  Quantum efficiency and optical throughput are dimensionless.  The adapter
  converts radiance to expected electrons using ``QE * throughput * lambda /
  (h*c)`` and integrates over wavelength.  Noise is represented only as an
  expected variance; no random realization or detection decision is made.
  """

  wavelengths_m: tuple[float, ...]
  quantum_efficiency: tuple[float, ...]
  optical_throughput: tuple[float, ...]
  dark_current_e_per_s: float = 0.0
  read_noise_std_e: float = 0.0
  response_id: str = 'detector-response-v1'

  def __post_init__(self) -> None:
    wavelengths = _positive_axis(self.wavelengths_m, 'detector wavelengths_m')
    quantum_efficiency = _finite_vector(
      self.quantum_efficiency,
      field_name='quantum_efficiency',
      minimum=0.0,
      maximum=1.0,
    )
    optical_throughput = _finite_vector(
      self.optical_throughput,
      field_name='optical_throughput',
      minimum=0.0,
      maximum=1.0,
    )
    if len(wavelengths) != len(quantum_efficiency) or len(wavelengths) != len(optical_throughput):
      raise ValueError('detector response arrays must have matching lengths')
    ####
    if not self.response_id:
      raise ValueError('response_id must not be empty')
    ####
    if not isfinite(self.dark_current_e_per_s) or self.dark_current_e_per_s < 0.0:
      raise ValueError('dark_current_e_per_s must be finite and nonnegative')
    ####
    if not isfinite(self.read_noise_std_e) or self.read_noise_std_e < 0.0:
      raise ValueError('read_noise_std_e must be finite and nonnegative')
    ####
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'quantum_efficiency', quantum_efficiency)
    object.__setattr__(self, 'optical_throughput', optical_throughput)
  ####

  @property
  def electron_response_per_joule(self) -> tuple[float, ...]:
    """Return the wavelength-dependent expected electrons per joule."""

    return tuple(
      quantum_efficiency * throughput * wavelength_m
      / (PLANCK_CONSTANT_J_S * SPEED_OF_LIGHT_M_PER_S)
      for wavelength_m, quantum_efficiency, throughput in zip(
        self.wavelengths_m,
        self.quantum_efficiency,
        self.optical_throughput,
        strict=True,
      )
    )
  ####
####


@dataclass(frozen=True, slots=True)
class FpaPixelImage:
  """Expected detector image produced by the explicit downstream operator."""

  width_px: int
  height_px: int
  wavelengths_m: tuple[float, ...]
  exposure_s: float
  expected_electrons: FloatMatrix
  dark_electrons: FloatMatrix
  noise_variance_e2: FloatMatrix
  validity_mask: tuple[tuple[bool, ...], ...]
  source_semantics: str
  detector_response_id: str
  camera_optics_id: str | None = None
  camera_mapping_model_id: str | None = None
  operator_id: str = FPA_PIXEL_DETECTOR_OPERATOR_ID
  atmospheric_path_operator_id: str | None = None
  atmospheric_path_layer_digest: str | None = None
  atmospheric_path_layer_ids: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    width = _positive_dimension(self.width_px, 'width_px')
    height = _positive_dimension(self.height_px, 'height_px')
    wavelengths = _positive_axis(self.wavelengths_m, 'wavelengths_m')
    if not isfinite(self.exposure_s) or self.exposure_s <= 0.0:
      raise ValueError('exposure_s must be finite and positive')
    ####
    expected = _matrix(
      self.expected_electrons,
      row_count=height,
      column_count=width,
      field_name='expected_electrons',
      minimum=0.0,
    )
    dark = _matrix(
      self.dark_electrons,
      row_count=height,
      column_count=width,
      field_name='dark_electrons',
      minimum=0.0,
    )
    variance = _matrix(
      self.noise_variance_e2,
      row_count=height,
      column_count=width,
      field_name='noise_variance_e2',
      minimum=0.0,
    )
    validity = _bool_matrix(
      self.validity_mask,
      row_count=height,
      column_count=width,
      field_name='validity_mask',
    )
    if not isinstance(self.source_semantics, str) or not self.source_semantics:
      raise ValueError('source_semantics must be a nonempty string')
    ####
    if not isinstance(self.detector_response_id, str) or not self.detector_response_id:
      raise ValueError('detector_response_id must be a nonempty string')
    ####
    if not isinstance(self.operator_id, str) or self.operator_id != FPA_PIXEL_DETECTOR_OPERATOR_ID:
      raise ValueError(f'operator_id must be {FPA_PIXEL_DETECTOR_OPERATOR_ID!r}')
    ####
    atmospheric_path_operator_id = _optional_identity(
      self.atmospheric_path_operator_id,
      'atmospheric_path_operator_id',
    )
    atmospheric_path_layer_digest = _optional_identity(
      self.atmospheric_path_layer_digest,
      'atmospheric_path_layer_digest',
    )
    atmospheric_path_layer_ids = tuple(self.atmospheric_path_layer_ids)
    if any(not isinstance(layer_id, str) or not layer_id for layer_id in atmospheric_path_layer_ids):
      raise ValueError('atmospheric_path_layer_ids must contain nonempty strings')
    ####
    if atmospheric_path_operator_id is not None:
      if atmospheric_path_operator_id != ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID:
        raise ValueError(
          f'atmospheric_path_operator_id must be {ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID!r}'
        )
      ####
      if atmospheric_path_layer_digest is None:
        raise ValueError('atmospheric_path_layer_digest is required with an atmospheric path operator')
      ####
    elif atmospheric_path_layer_digest is not None or atmospheric_path_layer_ids:
      raise ValueError('atmospheric path lineage requires its operator identity')
    ####
    object.__setattr__(self, 'width_px', width)
    object.__setattr__(self, 'height_px', height)
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'exposure_s', float(self.exposure_s))
    object.__setattr__(self, 'expected_electrons', expected)
    object.__setattr__(self, 'dark_electrons', dark)
    object.__setattr__(self, 'noise_variance_e2', variance)
    object.__setattr__(self, 'validity_mask', validity)
    object.__setattr__(self, 'camera_optics_id', _optional_identity(self.camera_optics_id, 'camera_optics_id'))
    object.__setattr__(self, 'camera_mapping_model_id', _optional_identity(self.camera_mapping_model_id, 'camera_mapping_model_id'))
    object.__setattr__(self, 'atmospheric_path_operator_id', atmospheric_path_operator_id)
    object.__setattr__(self, 'atmospheric_path_layer_digest', atmospheric_path_layer_digest)
    object.__setattr__(self, 'atmospheric_path_layer_ids', atmospheric_path_layer_ids)
  ####
####


@dataclass(frozen=True, slots=True)
class FpaDigitizationPolicy:
  """Deterministic expected-electron-to-counts policy.

  The policy describes an ADC transfer function only.  It does not sample
  shot/read noise, estimate detection probability, or turn an expected image
  into a measured image.
  """

  electrons_per_count: float
  offset_counts: float = 0.0
  bit_depth: int = 16
  rounding_mode: str = 'nearest_even'
  saturation_mode: str = 'clip'
  invalid_count: int = 0
  policy_id: str = 'fpa-digitization-v1'

  def __post_init__(self) -> None:
    if not isfinite(self.electrons_per_count) or self.electrons_per_count <= 0.0:
      raise ValueError('electrons_per_count must be finite and positive')
    ####
    if not isfinite(self.offset_counts):
      raise ValueError('offset_counts must be finite')
    ####
    if isinstance(self.bit_depth, bool) or not isinstance(self.bit_depth, int) or not 1 <= self.bit_depth <= 32:
      raise ValueError('bit_depth must be an integer from 1 through 32')
    ####
    if self.rounding_mode != 'nearest_even':
      raise ValueError('only nearest_even rounding_mode is supported')
    ####
    if self.saturation_mode != 'clip':
      raise ValueError('only clip saturation_mode is supported')
    ####
    if isinstance(self.invalid_count, bool) or not isinstance(self.invalid_count, int):
      raise ValueError('invalid_count must be an integer')
    ####
    if not 0 <= self.invalid_count <= self.full_scale_counts:
      raise ValueError('invalid_count must lie inside the ADC count range')
    ####
    if not self.policy_id:
      raise ValueError('policy_id must not be empty')
    ####
  ####

  @property
  def full_scale_counts(self) -> int:
    return (1 << self.bit_depth) - 1
  ####
####


@dataclass(frozen=True, slots=True)
class FpaDigitizedExpectation:
  """Deterministic ADC counts derived from an expected-electron image."""

  width_px: int
  height_px: int
  counts: tuple[tuple[int, ...], ...]
  validity_mask: BoolMatrix
  saturated_mask: BoolMatrix
  source_operator_id: str
  digitization_policy_id: str
  camera_optics_id: str | None = None
  camera_mapping_model_id: str | None = None
  operator_id: str = FPA_DIGITIZATION_OPERATOR_ID

  def __post_init__(self) -> None:
    width = _positive_dimension(self.width_px, 'width_px')
    height = _positive_dimension(self.height_px, 'height_px')
    counts = tuple(tuple(value for value in row) for row in self.counts)
    if len(counts) != height or any(len(row) != width for row in counts):
      raise ValueError(f'counts must have shape ({height}, {width})')
    ####
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for row in counts for value in row
    ):
      raise ValueError('counts must contain nonnegative integers')
    ####
    validity = _bool_matrix(
      self.validity_mask,
      row_count=height,
      column_count=width,
      field_name='validity_mask',
    )
    saturation = _bool_matrix(
      self.saturated_mask,
      row_count=height,
      column_count=width,
      field_name='saturated_mask',
    )
    if not isinstance(self.source_operator_id, str) or not self.source_operator_id:
      raise ValueError('source_operator_id must be a nonempty string')
    ####
    if not isinstance(self.digitization_policy_id, str) or not self.digitization_policy_id:
      raise ValueError('digitization_policy_id must be a nonempty string')
    ####
    if not isinstance(self.operator_id, str) or self.operator_id != FPA_DIGITIZATION_OPERATOR_ID:
      raise ValueError(f'operator_id must be {FPA_DIGITIZATION_OPERATOR_ID!r}')
    ####
    object.__setattr__(self, 'width_px', width)
    object.__setattr__(self, 'height_px', height)
    object.__setattr__(self, 'counts', counts)
    object.__setattr__(self, 'validity_mask', validity)
    object.__setattr__(self, 'saturated_mask', saturation)
    object.__setattr__(self, 'camera_optics_id', _optional_identity(self.camera_optics_id, 'camera_optics_id'))
    object.__setattr__(self, 'camera_mapping_model_id', _optional_identity(self.camera_mapping_model_id, 'camera_mapping_model_id'))
  ####
####


def _trapezoid_integral(axis: tuple[float, ...], values: tuple[float, ...]) -> float:
  return fsum(
    0.5 * (left + right) * (right_axis - left_axis)
    for left_axis, right_axis, left, right in zip(
      axis[:-1], axis[1:], values[:-1], values[1:], strict=True,
    )
  )
####


def integrate_ray_transfer_to_fpa(
    wavelengths_m: tuple[float, ...] | list[float],
    source_spectral_radiance: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    *,
    geometry: FpaPixelGeometry,
    detector: DetectorResponse,
    exposure_s: float,
    validity_mask: tuple[tuple[bool, ...], ...] | list[tuple[bool, ...]] | list[list[bool]] | None = None,
    background_transmittance: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]] | None = None,
    background_spectral_radiance: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]] | None = None,
) -> FpaPixelImage:
  """Integrate a ray-transfer source field into expected pixel electrons.

  Background composition is opt-in and requires both a background spectral
  radiance matrix and the ray-transfer transmittance matrix.  Pixels receiving
  any invalid contributing ray are marked invalid and their numeric outputs
  are zeroed, preventing partial batches from becoming apparently valid image
  evidence.
  """

  if not isfinite(exposure_s) or exposure_s <= 0.0:
    raise ValueError('exposure_s must be finite and positive')
  ####
  source_axis = _positive_axis(wavelengths_m, 'wavelengths_m')
  source_matrix = _matrix(
    source_spectral_radiance,
    row_count=len(geometry.ray_pixel_indices_row_col),
    column_count=len(source_axis),
    field_name='source_spectral_radiance',
    minimum=0.0,
  )
  sampled_source = sample_spectral_rows(
    source_axis,
    source_matrix,
    source_axis,
    validity_mask=validity_mask,
  )
  ray_count = len(source_matrix)
  mask = sampled_source.validity_mask
  background_included = (background_transmittance is not None) or (background_spectral_radiance is not None)
  if background_included and (background_transmittance is None or background_spectral_radiance is None):
    raise ValueError('background_transmittance and background_spectral_radiance must be supplied together')
  ####
  background_matrix: FloatMatrix | None = None
  transmittance_matrix: FloatMatrix | None = None
  if background_included:
    background_matrix = _matrix(
      background_spectral_radiance or (),
      row_count=ray_count,
      column_count=len(source_axis),
      field_name='background_spectral_radiance',
      minimum=0.0,
    )
    transmittance_matrix = _matrix(
      background_transmittance or (),
      row_count=ray_count,
      column_count=len(source_axis),
      field_name='background_transmittance',
      minimum=0.0,
      maximum=1.0,
    )
  ####
  if source_axis[0] < detector.wavelengths_m[0] or source_axis[-1] > detector.wavelengths_m[-1]:
    raise ValueError('detector response does not cover the requested wavelength domain')
  ####
  response_sample = sample_spectral_rows(
    detector.wavelengths_m,
    (detector.electron_response_per_joule,),
    source_axis,
  )
  if not all(response_sample.validity_mask[0]):
    raise ValueError('detector response does not cover the requested wavelength domain')
  ####
  signal_by_pixel = [
    [0.0 for _ in range(geometry.width_px)]
    for _ in range(geometry.height_px)
  ]
  pixel_validity = [
    [True for _ in range(geometry.width_px)]
    for _ in range(geometry.height_px)
  ]
  pixel_has_rays = [
    [False for _ in range(geometry.width_px)]
    for _ in range(geometry.height_px)
  ]
  for ray_index, ((row, column), weight) in enumerate(zip(
      geometry.ray_pixel_indices_row_col,
      geometry.ray_collection_weights_m2_sr,
      strict=True,
  )):
    pixel_has_rays[row][column] = True
    row_valid = all(mask[ray_index])
    pixel_validity[row][column] = pixel_validity[row][column] and row_valid
    if not row_valid:
      continue
    ####
    effective_radiance = list(sampled_source.values[ray_index])
    if background_included:
      assert background_matrix is not None
      assert transmittance_matrix is not None
      effective_radiance = [
        source + background * transmission
        for source, background, transmission in zip(
          effective_radiance,
          background_matrix[ray_index],
          transmittance_matrix[ray_index],
          strict=True,
        )
      ]
    ####
    spectral_electrons = tuple(
      radiance * weight * response
      for radiance, response in zip(
        effective_radiance,
        response_sample.values[0],
        strict=True,
      )
    )
    signal_by_pixel[row][column] += exposure_s * _trapezoid_integral(source_axis, spectral_electrons)
  ####
  expected_rows: list[tuple[float, ...]] = []
  dark_rows: list[tuple[float, ...]] = []
  variance_rows: list[tuple[float, ...]] = []
  validity_rows: list[tuple[bool, ...]] = []
  for row in range(geometry.height_px):
    expected_row: list[float] = []
    dark_row: list[float] = []
    variance_row: list[float] = []
    validity_row: list[bool] = []
    for column in range(geometry.width_px):
      valid = pixel_has_rays[row][column] and pixel_validity[row][column]
      dark = detector.dark_current_e_per_s * exposure_s if valid else 0.0
      expected = signal_by_pixel[row][column] + dark if valid else 0.0
      expected_row.append(expected)
      dark_row.append(dark)
      variance_row.append(expected + detector.read_noise_std_e**2 if valid else 0.0)
      validity_row.append(valid)
    ####
    expected_rows.append(tuple(expected_row))
    dark_rows.append(tuple(dark_row))
    variance_rows.append(tuple(variance_row))
    validity_rows.append(tuple(validity_row))
  ####
  return FpaPixelImage(
    width_px=geometry.width_px,
    height_px=geometry.height_px,
    wavelengths_m=source_axis,
    exposure_s=float(exposure_s),
    expected_electrons=tuple(expected_rows),
    dark_electrons=tuple(dark_rows),
    noise_variance_e2=tuple(variance_rows),
    validity_mask=tuple(validity_rows),
    source_semantics=(
      'source-plus-transmitted-background'
      if background_included else 'source-only'
    ),
    detector_response_id=detector.response_id,
    camera_optics_id=geometry.camera_optics_id,
    camera_mapping_model_id=geometry.camera_mapping_model_id,
  )
####


def integrate_spectral_ray_result_to_fpa(
    result: SpectralRayTransferResult,
    wavelengths_m: tuple[float, ...] | list[float],
    *,
    geometry: FpaPixelGeometry,
    detector: DetectorResponse,
    exposure_s: float,
    background_spectral_radiance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]]
    | None = None,
    atmospheric_path_layers: Sequence[AtmosphericPathLayer] | None = None,
) -> FpaPixelImage:
  """Adapt a lifecycle ray-transfer result into the deterministic FPA operator.

  The wavelength axis is supplied by the original ray request because the
  ray-transfer result intentionally carries matrix data but not request axes.
  When ``background_spectral_radiance`` is supplied, the result's explicit
  ``background_transmittance`` matrix is used to compose
  ``L_source + L_background * tau``.  When ``atmospheric_path_layers`` is
  supplied, that caller-owned homogeneous path is applied between the source
  and detector; its transmittance also attenuates the optional background
  contribution.  Neither option infers an atmosphere or a detector model.
  """

  if not isinstance(result, SpectralRayTransferResult):
    raise TypeError('result must be SpectralRayTransferResult')
  ####
  source_spectral_radiance = result.source_spectral_radiance
  validity_mask = result.validity_mask
  effective_background_transmittance = None
  path_applied = atmospheric_path_layers is not None
  selected_path_layers = None if atmospheric_path_layers is None else tuple(atmospheric_path_layers)
  if path_applied:
    transferred = apply_atmospheric_path_layers(
      wavelengths_m,
      source_spectral_radiance,
      selected_path_layers or (),
      validity_mask=validity_mask,
    )
    source_spectral_radiance = transferred.values
    validity_mask = transferred.validity_mask
    if background_spectral_radiance is not None:
      path_transfer = compose_atmospheric_path_layers(
        wavelengths_m,
        selected_path_layers or (),
      )
      effective_background_transmittance = tuple(
        tuple(
          plume_transmission * path_transmission
          for plume_transmission, path_transmission in zip(
            plume_row,
            path_transfer.transmittance,
            strict=True,
          )
        )
        for plume_row in result.background_transmittance
      )
    ####
  elif background_spectral_radiance is not None:
    effective_background_transmittance = result.background_transmittance
  ####
  image = integrate_ray_transfer_to_fpa(
    wavelengths_m,
    source_spectral_radiance,
    geometry=geometry,
    detector=detector,
    exposure_s=exposure_s,
    validity_mask=validity_mask,
    background_transmittance=effective_background_transmittance,
    background_spectral_radiance=background_spectral_radiance,
  )
  if not path_applied:
    return image
  ####
  semantics = (
    'source-after-explicit-atmospheric-path-plus-transmitted-background'
    if background_spectral_radiance is not None
    else 'source-after-explicit-atmospheric-path'
  )
  assert selected_path_layers is not None
  return replace(
    image,
    source_semantics=semantics,
    atmospheric_path_operator_id=ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID,
    atmospheric_path_layer_digest=canonical_digest(selected_path_layers),
    atmospheric_path_layer_ids=tuple(layer.layer_id for layer in selected_path_layers),
  )
####


def digitize_expected_electrons(
    image: FpaPixelImage,
    *,
    policy: FpaDigitizationPolicy,
) -> FpaDigitizedExpectation:
  """Apply an explicit deterministic ADC policy to expected electrons.

  Valid pixels are converted as ``round(electrons / scale + offset)`` using
  the declared nearest-even rule and then clipped to the declared ADC range.
  Invalid pixels receive ``policy.invalid_count`` and remain invalid.  The
  result is an expected digitized image, not a random detector realization.
  """

  if not isinstance(image, FpaPixelImage):
    raise TypeError('image must be FpaPixelImage')
  ####
  if not isinstance(policy, FpaDigitizationPolicy):
    raise TypeError('policy must be FpaDigitizationPolicy')
  ####
  expected = _matrix(
    image.expected_electrons,
    row_count=image.height_px,
    column_count=image.width_px,
    field_name='expected_electrons',
    minimum=0.0,
  )
  if len(image.validity_mask) != image.height_px or any(
      len(row) != image.width_px for row in image.validity_mask
  ):
    raise ValueError('validity_mask must match the declared image shape')
  ####
  counts_rows: list[tuple[int, ...]] = []
  saturation_rows: list[tuple[bool, ...]] = []
  for row_index in range(image.height_px):
    count_row: list[int] = []
    saturation_row: list[bool] = []
    for column_index in range(image.width_px):
      if not image.validity_mask[row_index][column_index]:
        count_row.append(policy.invalid_count)
        saturation_row.append(False)
        continue
      ####
      unbounded_count = round(
        expected[row_index][column_index] / policy.electrons_per_count
        + policy.offset_counts,
      )
      saturated = (
        unbounded_count < 0
        or unbounded_count > policy.full_scale_counts
      )
      count_row.append(min(max(unbounded_count, 0), policy.full_scale_counts))
      saturation_row.append(saturated)
    ####
    counts_rows.append(tuple(count_row))
    saturation_rows.append(tuple(saturation_row))
  ####
  return FpaDigitizedExpectation(
    width_px=image.width_px,
    height_px=image.height_px,
    counts=tuple(counts_rows),
    validity_mask=image.validity_mask,
    saturated_mask=tuple(saturation_rows),
    source_operator_id=image.operator_id,
    digitization_policy_id=policy.policy_id,
    camera_optics_id=image.camera_optics_id,
    camera_mapping_model_id=image.camera_mapping_model_id,
  )
####


__all__ = (
  'FPA_DIGITIZATION_OPERATOR_ID',
  'DetectorResponse',
  'FPA_PIXEL_DETECTOR_OPERATOR_ID',
  'FpaCameraOptics',
  'FpaDigitizationPolicy',
  'FpaDigitizedExpectation',
  'FpaPixelGeometry',
  'FpaPixelImage',
  'digitize_expected_electrons',
  'integrate_ray_transfer_to_fpa',
  'integrate_spectral_ray_result_to_fpa',
)
