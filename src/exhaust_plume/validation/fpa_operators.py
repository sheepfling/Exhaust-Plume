"""Deterministic downstream pixel/detector operators for ray-transfer results.

The adapter in this module is deliberately downstream of the optical product.
It converts source spectral radiance into expected detector electrons using
explicit ray collection weights, a detector response, and an exposure time.
It does not create a plume field, mutate the ray-transfer contract, sample
random noise, or advertise a focal-plane provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite

from exhaust_plume.validation.measurement_operators import sample_spectral_rows


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
    if isinstance(self.width_px, bool) or self.width_px < 1:
      raise ValueError('width_px must be a positive integer')
    ####
    if isinstance(self.height_px, bool) or self.height_px < 1:
      raise ValueError('height_px must be a positive integer')
    ####
    indices = tuple((int(row), int(column)) for row, column in self.ray_pixel_indices_row_col)
    if not indices:
      raise ValueError('ray_pixel_indices_row_col must not be empty')
    ####
    if any(
        row < 0 or row >= self.height_px or column < 0 or column >= self.width_px
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
  camera_optics_id: str | None
  camera_mapping_model_id: str | None
  operator_id: str = FPA_DIGITIZATION_OPERATOR_ID


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
)
