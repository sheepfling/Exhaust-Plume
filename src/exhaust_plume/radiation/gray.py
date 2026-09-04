"""Exact homogeneous gray segment transfer.

The source-function convention is

``L_out = L_in exp(-kappa * length) + S (1 - exp(-kappa * length))``.

Layer composition receives segments in near-observer to far-scene order.  It
returns the plume source contribution separately from the transmittance that
would multiply an external background radiance.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, expm1, isfinite
from typing import Sequence

__all__ = (
  'GrayTransferResult',
  'HomogeneousSegment',
  'compose_homogeneous_segments',
  'homogeneous_segment_transfer',
)


def _spectrum(value: Sequence[float], field_name: str) -> tuple[float, ...]:
  normalized = tuple(float(item) for item in value)
  if not normalized:
    raise ValueError(f'{field_name} must not be empty')
  ####
  if not all(isfinite(item) and item >= 0.0 for item in normalized):
    raise ValueError(f'{field_name} must be finite and nonnegative')
  ####
  return normalized
####


@dataclass(frozen=True, slots=True)
class HomogeneousSegment:
  """One homogeneous segment, expressed in near-to-far traversal order."""

  source_function_w_sr_m: tuple[float, ...]
  absorption_coefficient_per_m: tuple[float, ...]
  length_m: float

  def __post_init__(self) -> None:
    source = _spectrum(self.source_function_w_sr_m, 'source_function_w_sr_m')
    absorption = _spectrum(self.absorption_coefficient_per_m, 'absorption_coefficient_per_m')
    if len(source) != len(absorption):
      raise ValueError('source and absorption spectra must have matching lengths')
    ####
    if not isfinite(self.length_m) or self.length_m < 0.0:
      raise ValueError('segment length_m must be finite and nonnegative')
    ####
    object.__setattr__(self, 'source_function_w_sr_m', source)
    object.__setattr__(self, 'absorption_coefficient_per_m', absorption)
    object.__setattr__(self, 'length_m', float(self.length_m))
  ####
####


@dataclass(frozen=True, slots=True)
class GrayTransferResult:
  """Separated source contribution, background transmittance, and depth."""

  source_radiance_w_sr_m: tuple[float, ...]
  background_transmittance: tuple[float, ...]
  optical_depth: tuple[float, ...]

  def __post_init__(self) -> None:
    source = _spectrum(self.source_radiance_w_sr_m, 'source_radiance_w_sr_m')
    transmittance = tuple(float(item) for item in self.background_transmittance)
    depth = _spectrum(self.optical_depth, 'optical_depth')
    if len(source) != len(transmittance) or len(source) != len(depth):
      raise ValueError('gray transfer spectra must have matching lengths')
    ####
    if not all(isfinite(item) and 0.0 <= item <= 1.0 for item in transmittance):
      raise ValueError('background_transmittance must be finite and in [0, 1]')
    ####
    object.__setattr__(self, 'source_radiance_w_sr_m', source)
    object.__setattr__(self, 'background_transmittance', transmittance)
    object.__setattr__(self, 'optical_depth', depth)
  ####
####


def homogeneous_segment_transfer(
    source_function_w_sr_m: Sequence[float],
    absorption_coefficient_per_m: Sequence[float],
    length_m: float,
) -> GrayTransferResult:
  """Solve one homogeneous segment exactly for every wavelength."""

  segment = HomogeneousSegment(
    source_function_w_sr_m=tuple(source_function_w_sr_m),
    absorption_coefficient_per_m=tuple(absorption_coefficient_per_m),
    length_m=length_m,
  )
  source: list[float] = []
  transmittance: list[float] = []
  optical_depth: list[float] = []
  for source_function, absorption in zip(
      segment.source_function_w_sr_m,
      segment.absorption_coefficient_per_m,
  ):
    depth = absorption * segment.length_m
    transmission = exp(-depth)
    source.append(source_function * (-expm1(-depth)))
    transmittance.append(transmission)
    optical_depth.append(depth)
  ####
  return GrayTransferResult(tuple(source), tuple(transmittance), tuple(optical_depth))
####


def compose_homogeneous_segments(segments: Sequence[HomogeneousSegment]) -> GrayTransferResult:
  """Compose ordered homogeneous segments without mixing source/background terms."""

  if not segments:
    raise ValueError('at least one homogeneous segment is required')
  ####
  wavelength_count = len(segments[0].source_function_w_sr_m)
  source = [0.0] * wavelength_count
  transmittance = [1.0] * wavelength_count
  optical_depth = [0.0] * wavelength_count
  for segment in segments:
    if len(segment.source_function_w_sr_m) != wavelength_count:
      raise ValueError('all homogeneous segments must use the same wavelength count')
    ####
    segment_result = homogeneous_segment_transfer(
      segment.source_function_w_sr_m,
      segment.absorption_coefficient_per_m,
      segment.length_m,
    )
    for index in range(wavelength_count):
      # Segments are traversed from the observer toward the scene.  Emission
      # from a farther segment is attenuated by the already accumulated near
      # segments; the background term is the product of all transmissions.
      source[index] += segment_result.source_radiance_w_sr_m[index] * transmittance[index]
      transmittance[index] *= segment_result.background_transmittance[index]
      optical_depth[index] += segment_result.optical_depth[index]
    ####
  ####
  return GrayTransferResult(tuple(source), tuple(transmittance), tuple(optical_depth))
####
