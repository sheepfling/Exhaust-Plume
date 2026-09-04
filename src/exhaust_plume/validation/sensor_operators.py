"""Explicit downstream atmosphere and sensor-space operators.

The operators in this module consume already-produced spectral quantities. They
do not create a plume field, change the intrinsic signature contract, or infer
observer, atmosphere, or detector parameters that were not supplied by the
caller. Every reduction records its measurement semantics and propagates an
invalid result instead of silently integrating a partial batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, fsum, isfinite, pi, sqrt
from collections.abc import Sequence
from typing import Literal

from exhaust_plume.validation.measurement_operators import sample_spectral_rows
from exhaust_plume.radiation.gray import HomogeneousSegment, compose_homogeneous_segments


ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID = 'op.atmosphere.path-transfer'
BANDPASS_DETECTOR_OPERATOR_ID = 'op.sensor.bandpass-detector'
LOS_FOV_SPECTRUM_OPERATOR_ID = 'op.sensor.los-fov-spectrum'

FloatMatrix = tuple[tuple[float, ...], ...]
BoolMatrix = tuple[tuple[bool, ...], ...]
FovIntegrationMode = Literal['solid_angle_average', 'solid_angle_integral']


def _axis(values: tuple[float, ...] | list[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if not axis or any(not isfinite(value) or value <= 0.0 for value in axis):
    raise ValueError(f'{field_name} must be finite, positive, and non-empty')
  ####
  if any(right <= left for left, right in zip(axis, axis[1:])):
    raise ValueError(f'{field_name} must be strictly increasing')
  ####
  return axis
####


def _matrix(
    values: tuple[tuple[float, ...], ...] | list[tuple[float, ...]] | list[list[float]],
    *,
    column_count: int,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> FloatMatrix:
  matrix = tuple(tuple(float(value) for value in row) for row in values)
  if not matrix or any(len(row) != column_count for row in matrix):
    raise ValueError(f'{field_name} must be a non-empty rectangular matrix')
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


def _mask(
    validity_mask: tuple[tuple[bool, ...], ...]
    | list[tuple[bool, ...]]
    | list[list[bool]]
    | None,
    *,
    row_count: int,
    column_count: int,
) -> BoolMatrix:
  if validity_mask is None:
    return tuple((True,) * column_count for _ in range(row_count))
  ####
  mask = tuple(tuple(value for value in row) for row in validity_mask)
  if len(mask) != row_count or any(len(row) != column_count for row in mask):
    raise ValueError('validity_mask must match the matrix shape')
  ####
  if any(not isinstance(value, bool) for row in mask for value in row):
    raise ValueError('validity_mask must contain bool values')
  ####
  return mask
####


def _unit_direction(value: tuple[float, float, float] | list[float], field_name: str) -> tuple[float, float, float]:
  direction = tuple(float(component) for component in value)
  if len(direction) != 3 or not all(isfinite(component) for component in direction):
    raise ValueError(f'{field_name} must be a finite 3-vector')
  ####
  norm = sqrt(sum(component * component for component in direction))
  if abs(norm - 1.0) > 1.0e-6:
    raise ValueError(f'{field_name} must be unit length')
  ####
  return direction
####


@dataclass(frozen=True, slots=True)
class AtmosphericPathLayer:
  """One caller-supplied homogeneous atmospheric layer.

  Layers are supplied in near-observer to far-source order.  The source
  function and absorption coefficient are explicit optical inputs; this
  contract does not infer temperature, composition, scattering, or line
  spectra from altitude.
  """

  source_function_w_sr_m: tuple[float, ...]
  absorption_coefficient_per_m: tuple[float, ...]
  length_m: float
  layer_id: str = 'atmospheric-path-layer'

  def __post_init__(self) -> None:
    source = tuple(float(value) for value in self.source_function_w_sr_m)
    absorption = tuple(float(value) for value in self.absorption_coefficient_per_m)
    if not source or len(source) != len(absorption):
      raise ValueError('atmospheric layer spectra must have matching nonzero lengths')
    ####
    if any(not isfinite(value) or value < 0.0 for value in source + absorption):
      raise ValueError('atmospheric layer spectra must be finite and nonnegative')
    ####
    if not isfinite(self.length_m) or self.length_m < 0.0:
      raise ValueError('atmospheric layer length_m must be finite and nonnegative')
    ####
    if not self.layer_id:
      raise ValueError('atmospheric layer_id must not be empty')
    ####
    object.__setattr__(self, 'source_function_w_sr_m', source)
    object.__setattr__(self, 'absorption_coefficient_per_m', absorption)
    object.__setattr__(self, 'length_m', float(self.length_m))
  ####
####


@dataclass(frozen=True, slots=True)
class AtmosphericPathTransfer:
  """Composed atmospheric path source, transmittance, and optical depth."""

  wavelengths_m: tuple[float, ...]
  path_radiance_w_sr_m: tuple[float, ...]
  transmittance: tuple[float, ...]
  optical_depth: tuple[float, ...]
  layer_ids: tuple[str, ...]
  operator_id: str = ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID
####


def compose_atmospheric_path_layers(
    wavelengths_m: tuple[float, ...] | list[float],
    layers: Sequence[AtmosphericPathLayer],
) -> AtmosphericPathTransfer:
  """Compose explicit atmospheric layers in near-observer order.

  The returned ``path_radiance_w_sr_m`` is the atmospheric source contribution
  at the observer.  A plume/source radiance ``L_source`` is combined with it
  by ``L_observer = L_source * transmittance + path_radiance``.
  """

  wavelengths = _axis(wavelengths_m, 'wavelengths_m')
  selected_layers = tuple(layers)
  if not selected_layers:
    raise ValueError('atmospheric path requires at least one layer')
  ####
  if not all(isinstance(layer, AtmosphericPathLayer) for layer in selected_layers):
    raise TypeError('layers must contain AtmosphericPathLayer values')
  ####
  segments = []
  for index, layer in enumerate(selected_layers):
    if len(layer.source_function_w_sr_m) != len(wavelengths):
      raise ValueError(f'atmospheric layer {index} spectrum does not match wavelengths_m')
    ####
    segments.append(HomogeneousSegment(
      source_function_w_sr_m=layer.source_function_w_sr_m,
      absorption_coefficient_per_m=layer.absorption_coefficient_per_m,
      length_m=layer.length_m,
    ))
  ####
  transfer = compose_homogeneous_segments(tuple(segments))
  return AtmosphericPathTransfer(
    wavelengths_m=wavelengths,
    path_radiance_w_sr_m=transfer.source_radiance_w_sr_m,
    transmittance=transfer.background_transmittance,
    optical_depth=transfer.optical_depth,
    layer_ids=tuple(layer.layer_id for layer in selected_layers),
  )
####


def apply_atmospheric_path_layers(
    wavelengths_m: tuple[float, ...] | list[float],
    source_spectral_radiance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]],
    layers: Sequence[AtmosphericPathLayer],
    *,
    validity_mask: tuple[tuple[bool, ...], ...]
    | list[tuple[bool, ...]]
    | list[list[bool]]
    | None = None,
) -> PathTransferredSpectrum:
  """Apply one composed atmospheric path to every source-radiance row."""

  transfer = compose_atmospheric_path_layers(wavelengths_m, layers)
  source = _matrix(
    source_spectral_radiance,
    column_count=len(transfer.wavelengths_m),
    field_name='source_spectral_radiance',
    minimum=0.0,
  )
  return apply_atmospheric_path_transfer(
    transfer.wavelengths_m,
    source,
    (transfer.transmittance,) * len(source),
    validity_mask=validity_mask,
    path_radiance=(transfer.path_radiance_w_sr_m,) * len(source),
  )
####


@dataclass(frozen=True, slots=True)
class PathTransferredSpectrum:
  """A spectrum after explicit atmospheric/path transmission."""

  wavelengths_m: tuple[float, ...]
  values: FloatMatrix
  validity_mask: BoolMatrix
  source_semantics: str
  operator_id: str = ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID
####


def apply_atmospheric_path_transfer(
    wavelengths_m: tuple[float, ...] | list[float],
    source_spectral_radiance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]],
    transmittance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]],
    *,
    validity_mask: tuple[tuple[bool, ...], ...]
    | list[tuple[bool, ...]]
    | list[list[bool]]
    | None = None,
    path_radiance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]]
    | None = None,
) -> PathTransferredSpectrum:
  """Apply ``L_observer = L_source * tau + L_path`` row by row.

  ``path_radiance`` is already expressed at the observer. Omitting it is an
  explicit attenuated-source calculation, not an assumption that path radiance
  is zero in an external scenario.
  """

  wavelengths = _axis(wavelengths_m, 'wavelengths_m')
  source = _matrix(
    source_spectral_radiance,
    column_count=len(wavelengths),
    field_name='source_spectral_radiance',
    minimum=0.0,
  )
  path_transmission = _matrix(
    transmittance,
    column_count=len(wavelengths),
    field_name='transmittance',
    minimum=0.0,
    maximum=1.0,
  )
  if len(path_transmission) != len(source):
    raise ValueError('source_spectral_radiance and transmittance must have matching row counts')
  ####
  source_mask = _mask(
    validity_mask,
    row_count=len(source),
    column_count=len(wavelengths),
  )
  path = None
  if path_radiance is not None:
    path = _matrix(
      path_radiance,
      column_count=len(wavelengths),
      field_name='path_radiance',
      minimum=0.0,
    )
    if len(path) != len(source):
      raise ValueError('path_radiance must have the same row count as the source')
    ####
  ####
  output: list[tuple[float, ...]] = []
  output_mask: list[tuple[bool, ...]] = []
  for row_index, (row, tau_row, row_mask) in enumerate(zip(source, path_transmission, source_mask, strict=True)):
    path_row = (0.0,) * len(wavelengths) if path is None else path[row_index]
    valid = tuple(row_mask)
    output.append(
      tuple(
        row[index] * tau_row[index] + path_row[index] if valid[index] else 0.0
        for index in range(len(wavelengths))
      )
    )
    output_mask.append(valid)
  ####
  return PathTransferredSpectrum(
    wavelengths_m=wavelengths,
    values=tuple(output),
    validity_mask=tuple(output_mask),
    source_semantics='source-plus-path-radiance' if path is not None else 'attenuated-source',
  )
####


@dataclass(frozen=True, slots=True)
class SensorFovSpectrum:
  """A deterministic LOS/FOV reduction of ray spectral radiance."""

  wavelengths_m: tuple[float, ...]
  values: tuple[float, ...]
  validity_mask: tuple[bool, ...]
  selected_ray_indices: tuple[int, ...]
  selected_solid_angle_sr: float
  fov_half_angle_rad: float
  integration_mode: FovIntegrationMode
  output_units: str
  source_semantics: str
  operator_id: str = LOS_FOV_SPECTRUM_OPERATOR_ID
####


def integrate_los_fov_spectrum(
    wavelengths_m: tuple[float, ...] | list[float],
    ray_directions: tuple[tuple[float, float, float], ...]
    | list[tuple[float, float, float]],
    spectral_radiance: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]],
    *,
    observer_direction: tuple[float, float, float] | list[float],
    solid_angle_weights_sr: tuple[float, ...] | list[float],
    fov_half_angle_rad: float,
    validity_mask: tuple[tuple[bool, ...], ...]
    | list[tuple[bool, ...]]
    | list[list[bool]]
    | None = None,
    integration_mode: FovIntegrationMode = 'solid_angle_average',
    allow_partial_results: bool = False,
    source_semantics: str = 'source-only',
) -> SensorFovSpectrum:
  """Integrate radiance over a declared observer direction and FOV.

  ``solid_angle_average`` preserves radiance units. ``solid_angle_integral``
  returns the weighted angular integral and therefore has radiance-times-sr
  units. The caller must select the mode instead of relying on an implicit
  sensor convention.
  """

  wavelengths = _axis(wavelengths_m, 'wavelengths_m')
  directions = tuple(
    _unit_direction(direction, 'ray_directions')
    for direction in ray_directions
  )
  if not directions:
    raise ValueError('ray_directions must not be empty')
  ####
  source = _matrix(
    spectral_radiance,
    column_count=len(wavelengths),
    field_name='spectral_radiance',
    minimum=0.0,
  )
  if len(source) != len(directions):
    raise ValueError('ray_directions and spectral_radiance must have matching row counts')
  ####
  weights = tuple(float(weight) for weight in solid_angle_weights_sr)
  if len(weights) != len(directions) or any(not isfinite(weight) or weight <= 0.0 for weight in weights):
    raise ValueError('solid_angle_weights_sr must match rays and be finite and positive')
  ####
  if not isfinite(fov_half_angle_rad) or not 0.0 <= fov_half_angle_rad <= pi:
    raise ValueError('fov_half_angle_rad must be finite and in [0, pi]')
  ####
  if integration_mode not in ('solid_angle_average', 'solid_angle_integral'):
    raise ValueError('integration_mode must be solid_angle_average or solid_angle_integral')
  ####
  if not source_semantics:
    raise ValueError('source_semantics must not be empty')
  ####
  mask = _mask(validity_mask, row_count=len(source), column_count=len(wavelengths))
  observer = _unit_direction(observer_direction, 'observer_direction')
  cutoff = cos(fov_half_angle_rad)
  selected = tuple(
    index for index, direction in enumerate(directions)
    if sum(left * right for left, right in zip(direction, observer, strict=True)) >= cutoff - 1.0e-12
  )
  if not selected:
    raise ValueError('the declared FOV contains no rays')
  ####
  selected_weight = fsum(weights[index] for index in selected)
  selected_valid = all(all(mask[index]) for index in selected)
  if not selected_valid and not allow_partial_results:
    raise ValueError('the declared FOV contains invalid ray samples')
  ####
  if not selected_valid:
    output = (0.0,) * len(wavelengths)
    output_mask = (False,) * len(wavelengths)
  else:
    weighted = tuple(
      fsum(source[index][wavelength] * weights[index] for index in selected)
      for wavelength in range(len(wavelengths))
    )
    output = (
      tuple(value / selected_weight for value in weighted)
      if integration_mode == 'solid_angle_average'
      else weighted
    )
    output_mask = (True,) * len(wavelengths)
  ####
  return SensorFovSpectrum(
    wavelengths_m=wavelengths,
    values=output,
    validity_mask=output_mask,
    selected_ray_indices=selected,
    selected_solid_angle_sr=selected_weight,
    fov_half_angle_rad=float(fov_half_angle_rad),
    integration_mode=integration_mode,
    output_units=(
      'W m^-2 sr^-1 m^-1'
      if integration_mode == 'solid_angle_average'
      else 'W m^-2 m^-1'
    ),
    source_semantics=source_semantics,
  )
####


@dataclass(frozen=True, slots=True)
class BandpassDetectorSpectrum:
  """Bandpass-weighted spectral rows before any electron conversion."""

  band_min_m: float
  band_max_m: float
  values: tuple[float, ...]
  validity_mask: tuple[bool, ...]
  response_integral_m: float
  normalized_response: bool
  response_id: str
  operator_id: str = BANDPASS_DETECTOR_OPERATOR_ID
####


def integrate_bandpass_detector_rows(
    wavelengths_m: tuple[float, ...] | list[float],
    values: tuple[tuple[float, ...], ...]
    | list[tuple[float, ...]]
    | list[list[float]],
    response_wavelengths_m: tuple[float, ...] | list[float],
    response: tuple[float, ...] | list[float],
    *,
    band_min_m: float,
    band_max_m: float,
    validity_mask: tuple[tuple[bool, ...], ...]
    | list[tuple[bool, ...]]
    | list[list[bool]]
    | None = None,
    normalized_response: bool = False,
    response_id: str = 'bandpass-response-v1',
) -> BandpassDetectorSpectrum:
  """Integrate rows against an explicit detector response curve.

  The source and response curves are sampled only over their declared common
  band. No response extrapolation or out-of-band zero-filling is performed.
  ``normalized_response=True`` returns a response-weighted average rather than
  a response-weighted band integral.
  """

  source_axis = _axis(wavelengths_m, 'wavelengths_m')
  response_axis = _axis(response_wavelengths_m, 'response_wavelengths_m')
  if len(response_axis) != len(response):
    raise ValueError('response_wavelengths_m and response must have matching lengths')
  ####
  response_values = tuple(float(value) for value in response)
  if any(not isfinite(value) or value < 0.0 for value in response_values):
    raise ValueError('response must be finite and nonnegative')
  ####
  lower = float(band_min_m)
  upper = float(band_max_m)
  if not isfinite(lower) or not isfinite(upper) or lower <= 0.0 or upper <= lower:
    raise ValueError('band bounds must be finite, positive, and strictly increasing')
  ####
  if lower < source_axis[0] or upper > source_axis[-1]:
    raise ValueError('band is outside the source spectral domain')
  ####
  if lower < response_axis[0] or upper > response_axis[-1]:
    raise ValueError('band is outside the detector response domain')
  ####
  source = _matrix(values, column_count=len(source_axis), field_name='values', minimum=0.0)
  source_mask = _mask(validity_mask, row_count=len(source), column_count=len(source_axis))
  nodes = (lower, *(
    wavelength for wavelength in source_axis if lower < wavelength < upper
  ), upper)
  sampled_source = sample_spectral_rows(
    source_axis,
    source,
    nodes,
    validity_mask=source_mask,
  )
  sampled_response = sample_spectral_rows(
    response_axis,
    (response_values,),
    nodes,
  ).values[0]
  response_integral = fsum(
    0.5 * (left + right) * (right_node - left_node)
    for left, right, left_node, right_node in zip(
      sampled_response[:-1],
      sampled_response[1:],
      nodes[:-1],
      nodes[1:],
      strict=True,
    )
  )
  if not isfinite(response_integral) or response_integral <= 0.0:
    raise ValueError('detector response has zero integral over the declared band')
  ####
  results: list[float] = []
  result_masks: list[bool] = []
  for row, row_mask in zip(sampled_source.values, sampled_source.validity_mask, strict=True):
    if not all(row_mask):
      results.append(0.0)
      result_masks.append(False)
      continue
    ####
    response_product = tuple(value * weight for value, weight in zip(row, sampled_response, strict=True))
    area = fsum(
      0.5 * (left + right) * (right_node - left_node)
      for left, right, left_node, right_node in zip(
        response_product[:-1],
        response_product[1:],
        nodes[:-1],
        nodes[1:],
        strict=True,
      )
    )
    result = area / response_integral if normalized_response else area
    results.append(result)
    result_masks.append(isfinite(result) and result >= 0.0)
  ####
  if not response_id:
    raise ValueError('response_id must not be empty')
  ####
  return BandpassDetectorSpectrum(
    band_min_m=lower,
    band_max_m=upper,
    values=tuple(value if valid else 0.0 for value, valid in zip(results, result_masks, strict=True)),
    validity_mask=tuple(result_masks),
    response_integral_m=response_integral,
    normalized_response=normalized_response,
    response_id=response_id,
  )
####


__all__ = (
  'ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID',
  'AtmosphericPathLayer',
  'AtmosphericPathTransfer',
  'BANDPASS_DETECTOR_OPERATOR_ID',
  'BandpassDetectorSpectrum',
  'LOS_FOV_SPECTRUM_OPERATOR_ID',
  'PathTransferredSpectrum',
  'SensorFovSpectrum',
  'apply_atmospheric_path_transfer',
  'apply_atmospheric_path_layers',
  'compose_atmospheric_path_layers',
  'integrate_bandpass_detector_rows',
  'integrate_los_fov_spectrum',
)
