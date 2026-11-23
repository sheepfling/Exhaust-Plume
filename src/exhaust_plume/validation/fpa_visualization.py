"""Source-bound views for the deterministic downstream FPA operators.

The focal-plane array is deliberately not a fifth plume provider.  This
module consumes an explicit :class:`FpaPixelImage`, optional deterministic ADC
output, and an explicit upstream ray-result identity.  It exposes detector
arrays and declared image-plane metadata without inventing rays, optical depth,
noise realizations, detections, or validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from math import isfinite
from typing import Any, Literal, Mapping, TypeAlias

from pydantic import Field, model_validator

from exhaust_plume.api.contracts import SpectralRayTransferResult, StrictFrozenModel
from exhaust_plume.contracts.ray_transfer_v1 import SpectralRayTransferResult as ProviderRayTransferResult
from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.api.visualization_spec import (
  AxisScale,
  InvalidSamplePolicy,
  WavelengthDisplayUnit,
)
from exhaust_plume.validation.fpa_operators import (
  FPA_DIGITIZATION_OPERATOR_ID,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  FPA_POINT_SPREAD_OPERATOR_ID,
  DetectorResponse,
  FpaCameraOptics,
  FpaDigitizationPolicy,
  FpaDigitizedExpectation,
  FpaPixelImage,
  FpaRaySourceBinding,
)


FPA_VISUALIZATION_SPEC_SCHEMA = 'plume.visualization.fpa-spec@1'
FPA_VIEW_PROJECTION_SCHEMA = 'plume.visualization.fpa-view@1'
FPA_CLAIM_CEILING = (
  'Deterministic expected-electron and expected-ADC-count views only; '
  'no externally validated FPA image, measured detector-count, '
  'noise-realization, or detection claim.'
)

FloatMatrix: TypeAlias = tuple[tuple[float, ...], ...]
BoolMatrix: TypeAlias = tuple[tuple[bool, ...], ...]


class FpaDisplayLayer(str, Enum):
  """A declared quantity that may be shown in the pixel grid."""

  EXPECTED_ELECTRONS = 'expected_electrons'
  DARK_ELECTRONS = 'dark_electrons'
  NOISE_VARIANCE = 'noise_variance_e2'
  DIGITIZED_COUNTS = 'digitized_counts'
  VALIDITY_MASK = 'validity_mask'
  SATURATED_MASK = 'saturated_mask'
  DETECTOR_RESPONSE = 'detector_response'
####


class FpaSourceReference(StrictFrozenModel):
  """Identity and declared lineage of the upstream ray-transfer result."""

  source_kind: Literal['ray-transfer'] = 'ray-transfer'
  capability_id: str = Field(min_length=1)
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
  operator_chain: tuple[str, ...] = Field(
    default=(FPA_PIXEL_DETECTOR_OPERATOR_ID,),
    min_length=1,
  )

  @model_validator(mode='after')
  def validate_operator_chain(self) -> FpaSourceReference:
    if self.source_time_s is not None and not isfinite(self.source_time_s):
      raise ValueError('source_time_s must be finite when supplied')
    ####
    if self.operator_chain[0] != FPA_PIXEL_DETECTOR_OPERATOR_ID:
      raise ValueError(
        'FPA source operator_chain must begin with the pixel detector operator'
      )
    ####
    return self
  ####

  def validate_for_fpa(self) -> None:
    """Require a usable, explicitly in-domain source for deterministic FPA work.

    This check admits an operator-level preview. Production source eligibility
    is a separate, evidence-bound decision made by
    :func:`evaluate_fpa_source_admission`.
    """

    status = self.source_status.strip().casefold()
    if status not in {'ok', 'partial', 'degraded', 'inside', 'marginal'}:
      raise ValueError(
        f'ray-transfer status {self.source_status!r} is ineligible for FPA'
      )
    ####
    supported = self.source_applicability.get('supported')
    if supported is not None and not isinstance(supported, bool):
      raise ValueError('source applicability supported must be a bool when supplied')
    ####
    applicability_status = self.source_applicability.get('status')
    if applicability_status is not None:
      if not isinstance(applicability_status, str):
        raise ValueError('source applicability status must be a string when supplied')
      ####
      applicability_status = applicability_status.strip().casefold()
      if applicability_status not in {'inside', 'marginal'}:
        raise ValueError(
          f'ray-transfer applicability {applicability_status!r} is ineligible for FPA'
        )
    ####
    if supported is False:
      raise ValueError('an out-of-applicability ray-transfer source cannot feed FPA')
    ####
    if supported is not True and applicability_status is None:
      raise ValueError(
        'FPA requires an explicit supported or inside/marginal applicability declaration'
      )
    ####
  ####

  @property
  def ray_source_binding(self) -> FpaRaySourceBinding:
    """Return the compact image identity corresponding to this source."""

    return FpaRaySourceBinding(
      capability_id=self.capability_id,
      snapshot_id=self.snapshot_id,
      frame_id=self.frame_id,
      content_sha256=self.content_sha256,
    )
  ####

  @classmethod
  def from_ray_result(
    cls,
    result: SpectralRayTransferResult | ProviderRayTransferResult,
    *,
    operator_chain: tuple[str, ...] = (FPA_PIXEL_DETECTOR_OPERATOR_ID,),
  ) -> FpaSourceReference:
    """Capture a ray result's identity without copying its numerical payload."""

    if isinstance(result, ProviderRayTransferResult):
      metadata = result.metadata
      provenance = metadata.provenance
      return cls(
        capability_id=metadata.capability.wire_id,
        schema_version='1.0.0',
        provider_id=provenance.provider_id,
        session_id=metadata.snapshot.session_id,
        snapshot_id=metadata.snapshot.snapshot_id,
        source_time_s=metadata.snapshot.time_s,
        content_sha256=canonical_digest(result),
        frame_id=metadata.output_frame_id,
        source_status=metadata.applicability.status.value,
        source_fidelity=metadata.claims.model_dump(mode='json'),
        source_applicability={
          'status': metadata.applicability.status.value,
          'supported': metadata.applicability.status.value != 'outside',
          'reasons': list(metadata.applicability.reasons),
        },
        source_provenance={
          'model_lineage_id': provenance.model_lineage_id,
          'provider_id': provenance.provider_id,
          'provider_version': provenance.provider_version,
          'request_digest_sha256': metadata.request_digest_sha256,
          **dict(provenance.metadata),
        },
        operator_chain=operator_chain,
      )
    ####
    if not isinstance(result, SpectralRayTransferResult):
      raise TypeError('result must be a supported SpectralRayTransferResult')
    ####
    envelope = result.envelope
    return cls(
      capability_id=envelope.capability_id,
      schema_version=envelope.schema_version,
      provider_id=str(envelope.provider_id),
      session_id=str(envelope.session_id),
      snapshot_id=str(envelope.snapshot_id),
      content_sha256=envelope.content_sha256,
      frame_id=envelope.frame.frame_id,
      source_status=envelope.status.value,
      source_fidelity=envelope.fidelity.model_dump(mode='json'),
      source_applicability=envelope.applicability.model_dump(mode='json'),
      source_provenance=envelope.provenance.model_dump(mode='json'),
      operator_chain=operator_chain,
    )
  ####
####


class FpaSourceAdmissionStatus(str, Enum):
  """Result of checking a ray result against accepted FPA source evidence."""

  ADMITTED = 'admitted'
  BLOCKED_SOURCE_NOT_ELIGIBLE = 'blocked-source-not-eligible'
  BLOCKED_NO_QUALIFIED_RULE = 'blocked-no-qualified-rule'
  BLOCKED_SOURCE_METADATA = 'blocked-source-metadata'
####


@dataclass(frozen=True, slots=True)
class FpaSourceAdmissionRule:
  """Exact provider/fidelity/domain scope accepted by reviewed evidence."""

  rule_id: str
  capability_id: str
  provider_id: str
  source_fidelity_sha256: str
  applicability_domain_sha256: str
  evidence_id: str
  evidence_sha256: str

  def __post_init__(self) -> None:
    for name in ('rule_id', 'capability_id', 'provider_id', 'evidence_id'):
      value = getattr(self, name)
      if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
      ####
      object.__setattr__(self, name, value.strip())
    ####
    for name in (
      'source_fidelity_sha256',
      'applicability_domain_sha256',
      'evidence_sha256',
    ):
      value = getattr(self, name)
      if not isinstance(value, str) or len(value) != 64 or any(
          character not in '0123456789abcdef' for character in value
      ):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
      ####
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class FpaSourceAdmissionDecision:
  """Auditable source-specific FPA admission result."""

  status: FpaSourceAdmissionStatus
  capability_id: str
  provider_id: str
  snapshot_id: str
  source_content_sha256: str
  source_fidelity_sha256: str | None
  applicability_domain_sha256: str | None
  admission_rule_id: str | None = None
  evidence_id: str | None = None
  evidence_sha256: str | None = None
  reason: str = ''

  @property
  def admitted(self) -> bool:
    return self.status is FpaSourceAdmissionStatus.ADMITTED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'capability_id': self.capability_id,
      'provider_id': self.provider_id,
      'snapshot_id': self.snapshot_id,
      'source_content_sha256': self.source_content_sha256,
      'source_fidelity_sha256': self.source_fidelity_sha256,
      'applicability_domain_sha256': self.applicability_domain_sha256,
      'admission_rule_id': self.admission_rule_id,
      'evidence_id': self.evidence_id,
      'evidence_sha256': self.evidence_sha256,
      'admitted': self.admitted,
      'reason': self.reason,
    }
  ####
####


# No ray-transfer lane currently has accepted source-bound FPA evidence. Rules
# must be added only after the corresponding fidelity and operating domain
# pass independent source, camera, and detector validation.
FPA_SOURCE_ADMISSION_RULES: tuple[FpaSourceAdmissionRule, ...] = ()


def evaluate_fpa_source_admission(
  source: FpaSourceReference,
) -> FpaSourceAdmissionDecision:
  """Fail closed unless exact source fidelity/domain evidence is registered.

  This gate is intentionally separate from ``validate_for_fpa`` so local
  deterministic previews and operator diagnostics remain usable.
  """

  if not isinstance(source, FpaSourceReference):
    raise TypeError('source must be an FpaSourceReference')
  ####
  try:
    source.validate_for_fpa()
  except ValueError as error:
    return FpaSourceAdmissionDecision(
      status=FpaSourceAdmissionStatus.BLOCKED_SOURCE_NOT_ELIGIBLE,
      capability_id=source.capability_id,
      provider_id=source.provider_id,
      snapshot_id=source.snapshot_id,
      source_content_sha256=source.content_sha256,
      source_fidelity_sha256=None,
      applicability_domain_sha256=None,
      reason=str(error),
    )
  ####
  domain = source.source_applicability.get('domain', {})
  if not isinstance(domain, Mapping):
    return FpaSourceAdmissionDecision(
      status=FpaSourceAdmissionStatus.BLOCKED_SOURCE_METADATA,
      capability_id=source.capability_id,
      provider_id=source.provider_id,
      snapshot_id=source.snapshot_id,
      source_content_sha256=source.content_sha256,
      source_fidelity_sha256=None,
      applicability_domain_sha256=None,
      reason='source applicability domain must be a mapping',
    )
  ####
  try:
    fidelity_digest = canonical_digest(dict(source.source_fidelity))
    domain_digest = canonical_digest(dict(domain))
  except (TypeError, ValueError):
    return FpaSourceAdmissionDecision(
      status=FpaSourceAdmissionStatus.BLOCKED_SOURCE_METADATA,
      capability_id=source.capability_id,
      provider_id=source.provider_id,
      snapshot_id=source.snapshot_id,
      source_content_sha256=source.content_sha256,
      source_fidelity_sha256=None,
      applicability_domain_sha256=None,
      reason='source fidelity or applicability domain is not canonically digestible',
    )
  ####
  for rule in FPA_SOURCE_ADMISSION_RULES:
    if (
        rule.capability_id == source.capability_id
        and rule.provider_id == source.provider_id
        and rule.source_fidelity_sha256 == fidelity_digest
        and rule.applicability_domain_sha256 == domain_digest
    ):
      return FpaSourceAdmissionDecision(
        status=FpaSourceAdmissionStatus.ADMITTED,
        capability_id=source.capability_id,
        provider_id=source.provider_id,
        snapshot_id=source.snapshot_id,
        source_content_sha256=source.content_sha256,
        source_fidelity_sha256=fidelity_digest,
        applicability_domain_sha256=domain_digest,
        admission_rule_id=rule.rule_id,
        evidence_id=rule.evidence_id,
        evidence_sha256=rule.evidence_sha256,
        reason='exact provider, fidelity, and applicability domain match accepted evidence',
      )
    ####
  ####
  return FpaSourceAdmissionDecision(
    status=FpaSourceAdmissionStatus.BLOCKED_NO_QUALIFIED_RULE,
    capability_id=source.capability_id,
    provider_id=source.provider_id,
    snapshot_id=source.snapshot_id,
    source_content_sha256=source.content_sha256,
    source_fidelity_sha256=fidelity_digest,
    applicability_domain_sha256=domain_digest,
    reason='no accepted FPA source-evidence rule matches this provider, fidelity, and domain',
  )
####


class FpaViewSelection(StrictFrozenModel):
  """Linked pixel and spectral selections for an FPA view."""

  row_index: int | None = Field(default=None, ge=0)
  column_index: int | None = Field(default=None, ge=0)
  wavelength_index: int | None = Field(default=None, ge=0)
####


class FpaVisualizationSpec(StrictFrozenModel):
  """Reproducible view state bound to one downstream FPA input."""

  spec_schema: Literal['plume.visualization.fpa-spec@1'] = FPA_VISUALIZATION_SPEC_SCHEMA
  source: FpaSourceReference
  input_content_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
  view_kind: str = Field(pattern=r'^fpa\.[a-z][a-z0-9_.-]*$')
  selection: FpaViewSelection = Field(default_factory=FpaViewSelection)
  display_layer: FpaDisplayLayer = FpaDisplayLayer.EXPECTED_ELECTRONS
  invalid_sample_policy: InvalidSamplePolicy = InvalidSamplePolicy.GAP
  x_scale: AxisScale = AxisScale.LINEAR
  y_scale: AxisScale = AxisScale.LINEAR
  wavelength_display_unit: WavelengthDisplayUnit = WavelengthDisplayUnit.UM
  color_map: str = Field(default='magma', min_length=1)

  @classmethod
  def for_source(
    cls,
    source: FpaSourceReference,
    *,
    view_kind: str = 'fpa.overview',
    selection: FpaViewSelection | None = None,
    **overrides: Any,
  ) -> FpaVisualizationSpec:
    """Create a source-only spec for identity checks and migration handling.

    A source-only spec cannot project an FPA image. New render requests should
    use :meth:`for_input` so the image, detector, digitization, and camera data
    are all bound into the view identity.
    """

    return cls(
      source=source,
      view_kind=view_kind,
      selection=selection or FpaViewSelection(),
      **overrides,
    )
  ####

  @classmethod
  def for_input(
    cls,
    inputs: FpaVisualizationInput,
    *,
    view_kind: str = 'fpa.overview',
    selection: FpaViewSelection | None = None,
    **overrides: Any,
  ) -> FpaVisualizationSpec:
    """Create a view spec bound to the full numerical FPA input."""

    if not isinstance(inputs, FpaVisualizationInput):
      raise TypeError('inputs must be an FpaVisualizationInput')
    ####
    return cls(
      source=inputs.source,
      input_content_sha256=canonical_digest(inputs),
      view_kind=view_kind,
      selection=selection or FpaViewSelection(),
      **overrides,
    )
  ####

  def validate_for_source(self, source: FpaSourceReference) -> None:
    """Reject reuse of a view spec against another upstream result."""

    if self.source != source:
      raise ValueError('FPA visualization spec is bound to a different source result')
    ####
  ####

  def validate_for_input(self, inputs: FpaVisualizationInput) -> None:
    """Reject reuse against changed image, detector, camera, or count data."""

    if not isinstance(inputs, FpaVisualizationInput):
      raise TypeError('inputs must be an FpaVisualizationInput')
    ####
    self.validate_for_source(inputs.source)
    if self.input_content_sha256 is None:
      raise ValueError('FPA visualization spec must bind exact input content')
    ####
    if self.input_content_sha256 != canonical_digest(inputs):
      raise ValueError('FPA visualization spec is bound to different input content')
    ####
  ####

  def canonical_json(self) -> str:
    """Return deterministic JSON for storage and artifact manifests."""

    return json.dumps(
      self.model_dump(mode='json'),
      sort_keys=True,
      separators=(',', ':'),
      ensure_ascii=True,
      allow_nan=False,
    )
  ####

  def digest_sha256(self) -> str:
    """Return the identity of this exact FPA view state."""

    return hashlib.sha256(self.canonical_json().encode('utf-8')).hexdigest()
  ####
####


def _matrix_shape(
  values: tuple[tuple[float, ...], ...] | tuple[tuple[int, ...], ...] | BoolMatrix,
  *,
  height: int,
  width: int,
  field_name: str,
) -> None:
  if len(values) != height or any(len(row) != width for row in values):
    raise ValueError(f'{field_name} must have shape ({height}, {width})')
  ####
####


@dataclass(frozen=True, slots=True)
class FpaVisualizationInput:
  """Explicit numerical and metadata inputs for the FPA visualization lane."""

  image: FpaPixelImage
  source: FpaSourceReference
  detector_response: DetectorResponse | None = None
  digitized: FpaDigitizedExpectation | None = None
  digitization_policy: FpaDigitizationPolicy | None = None
  camera_optics: FpaCameraOptics | None = None
  claim_ceiling: str = FPA_CLAIM_CEILING
  validation_status: str = 'boundary-validated-downstream'

  def __post_init__(self) -> None:
    if not isinstance(self.image, FpaPixelImage):
      raise TypeError('image must be FpaPixelImage')
    ####
    if not isinstance(self.source, FpaSourceReference):
      raise TypeError('source must be FpaSourceReference')
    ####
    if self.source.capability_id != 'plume.optical.spectral-ray-transfer@1':
      raise ValueError('FPA visualization requires a spectral ray-transfer source')
    ####
    self.source.validate_for_fpa()
    if self.image.source_binding is None:
      raise ValueError('FPA visualization requires an image bound to its exact source result')
    ####
    if self.image.source_binding != self.source.ray_source_binding:
      raise ValueError('image source binding must match the FPA source reference')
    ####
    if self.image.operator_id != FPA_PIXEL_DETECTOR_OPERATOR_ID:
      raise ValueError('image must be produced by the FPA pixel detector operator')
    ####
    _matrix_shape(
      self.image.expected_electrons,
      height=self.image.height_px,
      width=self.image.width_px,
      field_name='expected_electrons',
    )
    _matrix_shape(
      self.image.dark_electrons,
      height=self.image.height_px,
      width=self.image.width_px,
      field_name='dark_electrons',
    )
    _matrix_shape(
      self.image.noise_variance_e2,
      height=self.image.height_px,
      width=self.image.width_px,
      field_name='noise_variance_e2',
    )
    _matrix_shape(
      self.image.validity_mask,
      height=self.image.height_px,
      width=self.image.width_px,
      field_name='validity_mask',
    )
    if not self.claim_ceiling or not self.validation_status:
      raise ValueError('claim_ceiling and validation_status must not be empty')
    ####
    if self.detector_response is not None and (
        self.detector_response.response_id != self.image.detector_response_id
    ):
      raise ValueError('detector_response identity must match image.detector_response_id')
    ####
    if self.camera_optics is not None and (
        self.camera_optics.camera_id != self.image.camera_optics_id
    ):
      raise ValueError('camera_optics identity must match image.camera_optics_id')
    ####
    point_spread_function = (
      None if self.camera_optics is None else self.camera_optics.point_spread_function
    )
    if self.image.point_spread_function_id is None:
      if point_spread_function is not None or self.image.point_spread_operator_id is not None:
        raise ValueError('camera PSF metadata must match the pixel image operator output')
    else:
      if point_spread_function is None:
        raise ValueError('FPA visualization requires the PSF metadata used by the image operator')
      ####
      if (
          self.image.point_spread_operator_id != FPA_POINT_SPREAD_OPERATOR_ID
          or self.image.point_spread_function_id != point_spread_function.model_id
          or self.image.point_spread_function_sha256 != point_spread_function.digest_sha256
      ):
        raise ValueError('camera PSF must match the exact image operator input')
      ####
    ####
    if self.digitized is None and self.digitization_policy is not None:
      raise ValueError('digitization_policy requires matching digitized output')
    ####
    if self.digitized is not None:
      if self.digitized.operator_id != FPA_DIGITIZATION_OPERATOR_ID:
        raise ValueError('digitized output must be produced by the FPA digitization operator')
      ####
      if (
          self.digitized.width_px != self.image.width_px
          or self.digitized.height_px != self.image.height_px
          or self.digitized.source_operator_id != self.image.operator_id
          or self.digitized.camera_optics_id != self.image.camera_optics_id
          or self.digitized.camera_mapping_model_id != self.image.camera_mapping_model_id
      ):
        raise ValueError('digitized output must preserve image shape and operator lineage')
      ####
      if self.digitized.validity_mask != self.image.validity_mask:
        raise ValueError('digitized output must preserve the image validity mask')
      ####
      _matrix_shape(
        self.digitized.counts,
        height=self.image.height_px,
        width=self.image.width_px,
        field_name='digitized counts',
      )
      _matrix_shape(
        self.digitized.validity_mask,
        height=self.image.height_px,
        width=self.image.width_px,
        field_name='digitized validity_mask',
      )
      _matrix_shape(
        self.digitized.saturated_mask,
        height=self.image.height_px,
        width=self.image.width_px,
        field_name='digitized saturated_mask',
      )
      if self.digitization_policy is None:
        raise ValueError('digitized output requires its explicit digitization policy')
      ####
      if self.digitized.digitization_policy_id != self.digitization_policy.policy_id:
        raise ValueError('digitization policy identity must match digitized output')
      ####
    ####
  ####

  @property
  def operator_ids(self) -> tuple[str, ...]:
    """Return the downstream operator chain represented by this input."""

    atmospheric_path = ()
    if self.image.atmospheric_path_operator_id is not None and (
        self.image.atmospheric_path_operator_id not in self.source.operator_chain
    ):
      atmospheric_path = (self.image.atmospheric_path_operator_id,)
    ####
    point_spread = (
      (FPA_POINT_SPREAD_OPERATOR_ID,)
      if self.image.point_spread_function_id is not None
      else ()
    )
    digitization = (FPA_DIGITIZATION_OPERATOR_ID,) if self.digitized is not None else ()
    return (*atmospheric_path, *point_spread, *self.source.operator_chain, *digitization)
  ####
####


@dataclass(frozen=True, slots=True)
class FpaPixelView:
  """One selected pixel with all available deterministic quantities."""

  row_index: int
  column_index: int
  valid: bool
  expected_electrons: float
  dark_electrons: float
  noise_variance_e2: float
  digitized_count: int | None
  saturated: bool | None
  image_plane_xy_m: tuple[float, float] | None
####


@dataclass(frozen=True, slots=True)
class FpaViewProjection:
  """Renderer-neutral arrays and linked selection for one FPA view."""

  schema: str
  view_spec_digest_sha256: str
  input_content_sha256: str
  source: FpaSourceReference
  width_px: int
  height_px: int
  wavelengths_m: tuple[float, ...]
  exposure_s: float
  source_semantics: str
  detector_response_id: str
  camera_optics_id: str | None
  camera_mapping_model_id: str | None
  operator_ids: tuple[str, ...]
  display_layer: FpaDisplayLayer
  layer_quantity: str
  layer_unit: str
  layer_axes: tuple[str, str]
  layer_values: FloatMatrix
  validity_mask: BoolMatrix
  digitized_counts: tuple[tuple[int, ...], ...] | None
  saturated_mask: BoolMatrix | None
  detector_wavelengths_m: tuple[float, ...] | None
  quantum_efficiency: tuple[float, ...] | None
  optical_throughput: tuple[float, ...] | None
  electron_response_per_joule: tuple[float, ...] | None
  selected_pixel: FpaPixelView
  selected_wavelength_m: float | None
  claim_ceiling: str
  validation_status: str
  atmospheric_path_operator_id: str | None = None
  atmospheric_path_layer_digest: str | None = None
  atmospheric_path_layer_ids: tuple[str, ...] = ()
  angular_projection_model_id: str | None = None
  on_axis_pixel_ifov_rad: tuple[float, float] | None = None
  field_of_view_rad: tuple[float, float] | None = None
  point_spread_operator_id: str | None = None
  point_spread_function_id: str | None = None
  point_spread_function_sha256: str | None = None
  point_spread_spectral_scope: str | None = None
  point_spread_edge_policy: str | None = None
  point_spread_kernel_weights: FloatMatrix | None = None

  def model_dump(self) -> dict[str, Any]:
    """Return JSON-compatible projection data for renderer adapters."""

    return {
      'schema': self.schema,
      'view_spec_digest_sha256': self.view_spec_digest_sha256,
      'input_content_sha256': self.input_content_sha256,
      'source': self.source.model_dump(mode='json'),
      'width_px': self.width_px,
      'height_px': self.height_px,
      'wavelengths_m': list(self.wavelengths_m),
      'exposure_s': self.exposure_s,
      'source_semantics': self.source_semantics,
      'detector_response_id': self.detector_response_id,
      'camera_optics_id': self.camera_optics_id,
      'camera_mapping_model_id': self.camera_mapping_model_id,
      'operator_ids': list(self.operator_ids),
      'display_layer': self.display_layer.value,
      'layer_quantity': self.layer_quantity,
      'layer_unit': self.layer_unit,
      'layer_axes': list(self.layer_axes),
      'layer_values': [list(row) for row in self.layer_values],
      'validity_mask': [list(row) for row in self.validity_mask],
      'digitized_counts': None if self.digitized_counts is None else [list(row) for row in self.digitized_counts],
      'saturated_mask': None if self.saturated_mask is None else [list(row) for row in self.saturated_mask],
      'detector_wavelengths_m': None if self.detector_wavelengths_m is None else list(self.detector_wavelengths_m),
      'quantum_efficiency': None if self.quantum_efficiency is None else list(self.quantum_efficiency),
      'optical_throughput': None if self.optical_throughput is None else list(self.optical_throughput),
      'electron_response_per_joule': None if self.electron_response_per_joule is None else list(self.electron_response_per_joule),
      'selected_pixel': {
        'row_index': self.selected_pixel.row_index,
        'column_index': self.selected_pixel.column_index,
        'valid': self.selected_pixel.valid,
        'expected_electrons': self.selected_pixel.expected_electrons,
        'dark_electrons': self.selected_pixel.dark_electrons,
        'noise_variance_e2': self.selected_pixel.noise_variance_e2,
        'digitized_count': self.selected_pixel.digitized_count,
        'saturated': self.selected_pixel.saturated,
        'image_plane_xy_m': self.selected_pixel.image_plane_xy_m,
      },
      'selected_wavelength_m': self.selected_wavelength_m,
      'claim_ceiling': self.claim_ceiling,
      'validation_status': self.validation_status,
      'atmospheric_path_operator_id': self.atmospheric_path_operator_id,
      'atmospheric_path_layer_digest': self.atmospheric_path_layer_digest,
      'atmospheric_path_layer_ids': list(self.atmospheric_path_layer_ids),
      'angular_projection_model_id': self.angular_projection_model_id,
      'on_axis_pixel_ifov_rad': (
        None
        if self.on_axis_pixel_ifov_rad is None
        else list(self.on_axis_pixel_ifov_rad)
      ),
      'field_of_view_rad': (
        None if self.field_of_view_rad is None else list(self.field_of_view_rad)
      ),
      'point_spread_operator_id': self.point_spread_operator_id,
      'point_spread_function_id': self.point_spread_function_id,
      'point_spread_function_sha256': self.point_spread_function_sha256,
      'point_spread_spectral_scope': self.point_spread_spectral_scope,
      'point_spread_edge_policy': self.point_spread_edge_policy,
      'point_spread_kernel_weights': (
        None
        if self.point_spread_kernel_weights is None
        else [list(row) for row in self.point_spread_kernel_weights]
      ),
    }
  ####
####


def _layer_semantics(layer: FpaDisplayLayer) -> tuple[str, str, tuple[str, str]]:
  """Declare the quantity, unit, and array axes for each FPA display layer."""

  if layer is FpaDisplayLayer.EXPECTED_ELECTRONS:
    return 'expected_photoelectrons', 'electron', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.DARK_ELECTRONS:
    return 'dark_electrons', 'electron', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.NOISE_VARIANCE:
    return 'noise_variance', 'electron^2', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.DIGITIZED_COUNTS:
    return 'digitized_counts', 'count', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.VALIDITY_MASK:
    return 'pixel_validity', '1', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.SATURATED_MASK:
    return 'pixel_saturation', '1', ('row_px', 'column_px')
  ####
  if layer is FpaDisplayLayer.DETECTOR_RESPONSE:
    return 'electron_response_per_joule', 'electron/J', ('wavelength_m', 'response_sample')
  ####
  raise ValueError(f'unsupported FPA display layer: {layer!r}')
####


def _layer_values(
  inputs: FpaVisualizationInput,
  layer: FpaDisplayLayer,
) -> tuple[tuple[float, ...], ...]:
  image = inputs.image
  if layer is FpaDisplayLayer.EXPECTED_ELECTRONS:
    return image.expected_electrons
  ####
  if layer is FpaDisplayLayer.DARK_ELECTRONS:
    return image.dark_electrons
  ####
  if layer is FpaDisplayLayer.NOISE_VARIANCE:
    return image.noise_variance_e2
  ####
  if layer is FpaDisplayLayer.VALIDITY_MASK:
    return tuple(tuple(1.0 if value else 0.0 for value in row) for row in image.validity_mask)
  ####
  if layer is FpaDisplayLayer.DIGITIZED_COUNTS:
    if inputs.digitized is None:
      raise ValueError('digitized_counts view requires explicit digitized output')
    ####
    return tuple(tuple(float(value) for value in row) for row in inputs.digitized.counts)
  ####
  if layer is FpaDisplayLayer.SATURATED_MASK:
    if inputs.digitized is None:
      raise ValueError('saturated_mask view requires explicit digitized output')
    ####
    return tuple(tuple(1.0 if value else 0.0 for value in row) for row in inputs.digitized.saturated_mask)
  ####
  if layer is FpaDisplayLayer.DETECTOR_RESPONSE:
    raise ValueError('detector_response is a spectral curve, not a pixel-grid layer')
  ####
  raise AssertionError(f'unhandled FPA display layer: {layer}')
####


def _selected_pixel(
  inputs: FpaVisualizationInput,
  selection: FpaViewSelection,
) -> FpaPixelView:
  image = inputs.image
  row = 0 if selection.row_index is None else selection.row_index
  column = 0 if selection.column_index is None else selection.column_index
  if row >= image.height_px or column >= image.width_px:
    raise IndexError('selected FPA pixel lies outside the declared image grid')
  ####
  plane_xy = None
  if inputs.camera_optics is not None:
    plane_xy = (
      (column - inputs.camera_optics.principal_point_px[0]) * inputs.camera_optics.pixel_pitch_m[0],
      (row - inputs.camera_optics.principal_point_px[1]) * inputs.camera_optics.pixel_pitch_m[1],
    )
  ####
  digitized_count = None
  saturated = None
  if inputs.digitized is not None:
    digitized_count = inputs.digitized.counts[row][column]
    saturated = inputs.digitized.saturated_mask[row][column]
  ####
  return FpaPixelView(
    row_index=row,
    column_index=column,
    valid=inputs.image.validity_mask[row][column],
    expected_electrons=inputs.image.expected_electrons[row][column],
    dark_electrons=inputs.image.dark_electrons[row][column],
    noise_variance_e2=inputs.image.noise_variance_e2[row][column],
    digitized_count=digitized_count,
    saturated=saturated,
    image_plane_xy_m=plane_xy,
  )
####


def project_fpa_view(
  inputs: FpaVisualizationInput,
  spec: FpaVisualizationSpec,
) -> FpaViewProjection:
  """Resolve a source-bound FPA spec into renderer-neutral arrays."""

  if not isinstance(inputs, FpaVisualizationInput):
    raise TypeError('inputs must be FpaVisualizationInput')
  ####
  if not isinstance(spec, FpaVisualizationSpec):
    raise TypeError('spec must be FpaVisualizationSpec')
  ####
  spec.validate_for_input(inputs)
  assert spec.input_content_sha256 is not None
  if spec.display_layer is FpaDisplayLayer.DETECTOR_RESPONSE:
    if inputs.detector_response is None:
      raise ValueError('detector_response view requires explicit DetectorResponse')
    ####
    layer_values = tuple(
      (value,)
      for value in inputs.detector_response.electron_response_per_joule
    )
    layer_validity = tuple((True,) for _value in layer_values)
  else:
    layer_values = _layer_values(inputs, spec.display_layer)
    layer_validity = inputs.image.validity_mask
  ####
  invalid_count = sum(
    1 for row in layer_validity for valid in row if not valid
  )
  if invalid_count and spec.invalid_sample_policy is InvalidSamplePolicy.REJECT:
    raise ValueError(f'FPA image contains {invalid_count} invalid pixels')
  ####
  selected = _selected_pixel(inputs, spec.selection)
  wavelength_index = spec.selection.wavelength_index
  if wavelength_index is None:
    wavelength_index = 0
  ####
  if wavelength_index >= len(inputs.image.wavelengths_m):
    raise IndexError('selected FPA wavelength lies outside the image spectral grid')
  ####
  selected_wavelength = inputs.image.wavelengths_m[wavelength_index]
  detector_wavelengths = None
  quantum_efficiency = None
  optical_throughput = None
  electron_response = None
  if inputs.detector_response is not None:
    detector_wavelengths = inputs.detector_response.wavelengths_m
    quantum_efficiency = inputs.detector_response.quantum_efficiency
    optical_throughput = inputs.detector_response.optical_throughput
    electron_response = inputs.detector_response.electron_response_per_joule
  ####
  layer_quantity, layer_unit, layer_axes = _layer_semantics(spec.display_layer)
  point_spread_function = (
    None if inputs.camera_optics is None else inputs.camera_optics.point_spread_function
  )
  return FpaViewProjection(
    schema=FPA_VIEW_PROJECTION_SCHEMA,
    view_spec_digest_sha256=spec.digest_sha256(),
    input_content_sha256=spec.input_content_sha256,
    source=inputs.source,
    width_px=inputs.image.width_px,
    height_px=inputs.image.height_px,
    wavelengths_m=inputs.image.wavelengths_m,
    exposure_s=inputs.image.exposure_s,
    source_semantics=inputs.image.source_semantics,
    detector_response_id=inputs.image.detector_response_id,
    camera_optics_id=inputs.image.camera_optics_id,
    camera_mapping_model_id=inputs.image.camera_mapping_model_id,
    operator_ids=inputs.operator_ids,
    display_layer=spec.display_layer,
    layer_quantity=layer_quantity,
    layer_unit=layer_unit,
    layer_axes=layer_axes,
    layer_values=layer_values,
    validity_mask=layer_validity,
    digitized_counts=None if inputs.digitized is None else inputs.digitized.counts,
    saturated_mask=None if inputs.digitized is None else inputs.digitized.saturated_mask,
    detector_wavelengths_m=detector_wavelengths,
    quantum_efficiency=quantum_efficiency,
    optical_throughput=optical_throughput,
    electron_response_per_joule=electron_response,
    selected_pixel=selected,
    selected_wavelength_m=selected_wavelength,
    claim_ceiling=inputs.claim_ceiling,
    validation_status=inputs.validation_status,
    atmospheric_path_operator_id=inputs.image.atmospheric_path_operator_id,
    atmospheric_path_layer_digest=inputs.image.atmospheric_path_layer_digest,
    atmospheric_path_layer_ids=inputs.image.atmospheric_path_layer_ids,
    angular_projection_model_id=(
      None
      if inputs.camera_optics is None
      else inputs.camera_optics.angular_projection_model_id
    ),
    on_axis_pixel_ifov_rad=(
      None
      if inputs.camera_optics is None
      else inputs.camera_optics.on_axis_pixel_ifov_rad
    ),
    field_of_view_rad=(
      None
      if inputs.camera_optics is None
      else inputs.camera_optics.field_of_view_rad(
        width_px=inputs.image.width_px,
        height_px=inputs.image.height_px,
      )
    ),
    point_spread_operator_id=inputs.image.point_spread_operator_id,
    point_spread_function_id=inputs.image.point_spread_function_id,
    point_spread_function_sha256=inputs.image.point_spread_function_sha256,
    point_spread_spectral_scope=(
      None if point_spread_function is None else point_spread_function.spectral_scope
    ),
    point_spread_edge_policy=(
      None if point_spread_function is None else point_spread_function.edge_policy
    ),
    point_spread_kernel_weights=(
      None if point_spread_function is None else point_spread_function.kernel_weights
    ),
  )
####


__all__ = (
  'FPA_CLAIM_CEILING',
  'FPA_SOURCE_ADMISSION_RULES',
  'FPA_VIEW_PROJECTION_SCHEMA',
  'FPA_VISUALIZATION_SPEC_SCHEMA',
  'FpaDisplayLayer',
  'FpaPixelView',
  'FpaSourceAdmissionDecision',
  'FpaSourceAdmissionRule',
  'FpaSourceAdmissionStatus',
  'FpaSourceReference',
  'FpaViewProjection',
  'FpaViewSelection',
  'FpaVisualizationInput',
  'FpaVisualizationSpec',
  'evaluate_fpa_source_admission',
  'project_fpa_view',
)
