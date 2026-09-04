"""Local contract checks for the bounded Visualization and Signature lanes.

These checks are intentionally narrower than external validation.  They make
the local release evidence prove that a provider stayed inside its declared
product contract, while leaving corpus-specific measurement and scenario gates
to the provider-comparison preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from exhaust_plume.contracts import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  RadiationClaim,
  SampleStatusCode,
  SpectralSignatureRequest,
  TimeModel,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
)
from exhaust_plume.contracts.signature_v1 import SpectralSignatureResult


_NORMALIZED_VISUAL_CHANNELS = frozenset({
  'core_radius_fraction',
  'emission_weight',
  'mixing_weight',
  'opacity_weight',
  'shock_weight',
  'turbulence_weight',
})


@dataclass(frozen=True, slots=True)
class VisualLaneInvariantReport:
  """Evidence that one straight visual result stayed inside its lane ceiling."""

  status: str
  section_count: int
  finite_positive_geometry: bool
  straight_axis_centerline: bool
  arc_length_strictly_increasing: bool
  section_limit_respected: bool
  axial_extent_respected: bool
  channel_lengths_match: bool
  normalized_channels_bounded: bool
  claim_ceiling_preserved: bool
  reasons: tuple[str, ...] = ()
####


@dataclass(frozen=True, slots=True)
class SignatureLaneInvariantReport:
  """Evidence that one signature result retained table and provenance limits."""

  status: str
  matrix_shape_matches_request: bool
  all_requested_samples_valid: bool
  uncertainty_shape_matches: bool
  asset_provenance_present: bool
  asset_identity_matches: bool
  no_extrapolation_used: bool
  claim_ceiling_preserved: bool
  reasons: tuple[str, ...] = ()
####


def validate_straight_visual_result(
    result: VisualSectionedTubeResult,
    request: VisualSectionedTubeRequest,
    *,
    expected_output_frame_id: str,
    centerline_tolerance_m: float = 1.0e-9,
) -> VisualLaneInvariantReport:
  """Check geometry and claims for the frozen straight visual lane.

  The centerline check is specific to this lane.  It is not a general rule for
  future curved-plume providers, which must use a separate fidelity lane.
  """

  sections = result.sections
  section_count = len(sections)
  finite_positive_geometry = all(
    all(isfinite(value) for value in (*section.center_m, section.arc_length_m))
    and isfinite(section.radius_major_m)
    and isfinite(section.radius_minor_m)
    and section.radius_major_m > 0.0
    and section.radius_minor_m > 0.0
    for section in sections
  )
  arc_lengths = tuple(section.arc_length_m for section in sections)
  arc_length_strictly_increasing = all(
    right > left for left, right in zip(arc_lengths, arc_lengths[1:])
  )
  straight_axis_centerline = all(
    abs(section.center_m[1]) <= centerline_tolerance_m
    and abs(section.center_m[2]) <= centerline_tolerance_m
    for section in sections
  )
  section_limit_respected = section_count <= request.sampling.maximum_section_count
  requested_extent = request.sampling.maximum_axial_extent_m
  axial_extent_respected = (
    requested_extent is None
    or (
      result.summary.length_m <= requested_extent + centerline_tolerance_m
      and (not sections or sections[-1].arc_length_m <= requested_extent + centerline_tolerance_m)
    )
  )
  channel_lengths_match = all(
    len(values) == section_count for values in result.channels.values()
  )
  normalized_channels_bounded = all(
    all(0.0 <= value <= 1.0 for value in values)
    for name, values in result.channels.items()
    if name in _NORMALIZED_VISUAL_CHANNELS
  )
  claim_ceiling_preserved = (
    result.metadata.output_frame_id == expected_output_frame_id
    and result.metadata.capability.wire_id == 'plume.visual.sectioned-tube@1'
    and result.metadata.applicability.status is not ApplicabilityStatus.OUTSIDE
    and result.metadata.claims.geometry is GeometryClaim.ENGINEERING_APPROXIMATE
    and result.metadata.claims.radiation is RadiationClaim.APPEARANCE_ONLY
    and result.metadata.claims.time_model is TimeModel.STEADY
  )
  checks = {
    'finite_positive_geometry': finite_positive_geometry,
    'straight_axis_centerline': straight_axis_centerline,
    'arc_length_strictly_increasing': arc_length_strictly_increasing,
    'section_limit_respected': section_limit_respected,
    'axial_extent_respected': axial_extent_respected,
    'channel_lengths_match': channel_lengths_match,
    'normalized_channels_bounded': normalized_channels_bounded,
    'claim_ceiling_preserved': claim_ceiling_preserved,
  }
  reasons = tuple(name for name, passed in checks.items() if not passed)
  return VisualLaneInvariantReport(
    status='passed' if not reasons else 'failed',
    section_count=section_count,
    **checks,
    reasons=reasons,
  )
####


def validate_signature_table_result(
    result: SpectralSignatureResult,
    request: SpectralSignatureRequest,
    *,
    expected_asset_id: str,
    expected_asset_sha256: str,
) -> SignatureLaneInvariantReport:
  """Check shape, provenance, and no-extrapolation behavior for a table result."""

  row_count = len(result.spectral_radiant_intensity)
  column_count = len(result.spectral_radiant_intensity[0]) if row_count else 0
  matrix_shape_matches_request = (
    (row_count, column_count)
    == (len(request.source_to_observer_directions), len(request.wavelengths_m))
    and len(result.validity_mask) == row_count
    and all(len(row) == column_count for row in result.validity_mask)
  )
  all_requested_samples_valid = (
    matrix_shape_matches_request
    and all(all(row) for row in result.validity_mask)
    and all(status.code is SampleStatusCode.OK for status in result.direction_status)
  )
  uncertainty = result.absolute_standard_uncertainty
  uncertainty_shape_matches = uncertainty is None or (
    len(uncertainty) == row_count
    and all(len(row) == column_count for row in uncertainty)
  )
  provenance = result.metadata.provenance
  provenance_metadata = provenance.metadata
  asset_provenance_present = bool(provenance.asset_digests_sha256) and bool(
    provenance_metadata.get('asset_id')
  )
  asset_identity_matches = (
    provenance.asset_digests_sha256 == (expected_asset_sha256,)
    and provenance_metadata.get('asset_id') == expected_asset_id
    and provenance_metadata.get('asset_digest_kind') == 'content_sha256'
  )
  no_extrapolation_used = (
    provenance_metadata.get('extrapolation_policy') == 'reject'
    and result.metadata.applicability.status is not ApplicabilityStatus.OUTSIDE
    and 'explicit table extrapolation enabled' not in result.metadata.warnings
  )
  claim_ceiling_preserved = (
    result.metadata.capability.wire_id == 'plume.signature.spectral-radiant-intensity@1'
    and result.metadata.claims.geometry is GeometryClaim.NOT_APPLICABLE
    and result.metadata.claims.radiation is RadiationClaim.TABULATED
    and result.metadata.claims.derivation is Derivation.TABULATED
    and result.metadata.claims.consistency is ConsistencyLevel.INDEPENDENT
  )
  checks = {
    'matrix_shape_matches_request': matrix_shape_matches_request,
    'all_requested_samples_valid': all_requested_samples_valid,
    'uncertainty_shape_matches': uncertainty_shape_matches,
    'asset_provenance_present': asset_provenance_present,
    'asset_identity_matches': asset_identity_matches,
    'no_extrapolation_used': no_extrapolation_used,
    'claim_ceiling_preserved': claim_ceiling_preserved,
  }
  reasons = tuple(name for name, passed in checks.items() if not passed)
  return SignatureLaneInvariantReport(
    status='passed' if not reasons else 'failed',
    **checks,
    reasons=reasons,
  )
####


__all__ = (
  'SignatureLaneInvariantReport',
  'VisualLaneInvariantReport',
  'validate_signature_table_result',
  'validate_straight_visual_result',
)
