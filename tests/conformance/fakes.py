"""Small canonical providers used to test the conformance harness itself."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from exhaust_plume.api import v1
from exhaust_plume.contracts.errors import ProviderClosedError

ROOT = Path(__file__).resolve().parents[2]
_POSE = v1.Pose(
  frame_id='world',
  translation_m=(0.0, 0.0, 0.0),
  rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
)


def _load_result(filename: str, result_type: type[Any]) -> Any:
  payload = (ROOT / 'fixtures' / 'contracts' / filename).read_text(encoding='utf-8')
  return result_type.model_validate(json.loads(payload))
  ####


def _request_frame(request: v1.ApiModel) -> str:
  for field_name in ('output_frame_id', 'direction_frame_id', 'ray_frame_id'):
    frame_id = getattr(request, field_name, None)
    if frame_id is not None:
      return frame_id
  raise AssertionError(f'fixture request has no frame identity: {type(request).__name__}')
  ####


@dataclass(frozen=True, slots=True)
class _FixtureEvaluator:
  result: Any
  provider_id: str
  provider_version: str

  def evaluate(self, request: v1.ApiModel, snapshot: v1.SnapshotMetadata) -> Any:
    request_digest = v1.canonical_digest(request)
    provenance = self.result.metadata.provenance.model_copy(update={
      'provider_id': self.provider_id,
      'provider_version': self.provider_version,
    })
    metadata = self.result.metadata.model_copy(update={
      'result_id': v1.canonical_digest({
        'snapshot': snapshot.snapshot_id,
        'request': request_digest,
      })[:24],
      'request_digest_sha256': request_digest,
      'snapshot': snapshot,
      'output_frame_id': _request_frame(request),
      'provenance': provenance,
    })
    return self.result.model_copy(update={'metadata': metadata})
  ####


class _FixtureSession:
  def __init__(
      self,
      *,
      provider_id: str,
      provider_version: str,
      capability: v1.CapabilityIdentity | None,
      result: Any | None,
  ) -> None:
    self._provider_id = provider_id
    self._provider_version = provider_version
    self._capability = capability
    self._result = result
    self._closed = False
    configuration_digest = v1.canonical_digest({
      'provider_id': provider_id,
      'provider_version': provider_version,
    })
    self._metadata = v1.SessionMetadata(
      session_id=v1.canonical_digest({
        'provider_id': provider_id,
        'provider_version': provider_version,
      })[:24],
      provider_id=provider_id,
      provider_version=provider_version,
      configuration_digest_sha256=configuration_digest,
    )
  ####

  @property
  def metadata(self) -> v1.SessionMetadata:
    return self._metadata
  ####

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: v1.Pose,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> v1.ProductSnapshot:
    if self._closed:
      raise ProviderClosedError('fixture session is closed')
    dynamic_digest = v1.canonical_digest(dynamic_state)
    ambient_digest = v1.canonical_digest(ambient_state)
    snapshot_metadata = v1.SnapshotMetadata(
      snapshot_id=v1.canonical_digest({
        'session': self._metadata.session_id,
        'time_s': time_s,
        'source_pose': source_pose,
        'dynamic': dynamic_digest,
        'ambient': ambient_digest,
      })[:24],
      session_id=self._metadata.session_id,
      time_s=time_s,
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=v1.canonical_digest({
        'provider_id': self._provider_id,
        'provider_version': self._provider_version,
      }),
    )
    evaluators: dict[v1.CapabilityIdentity, Any] = {}
    if self._capability is not None and self._result is not None:
      evaluators[self._capability] = _FixtureEvaluator(
        result=self._result,
        provider_id=self._provider_id,
        provider_version=self._provider_version,
      )
    return v1.ImmutableProductSnapshot(metadata=snapshot_metadata, _evaluators=evaluators)
  ####

  def close(self) -> None:
    self._closed = True
  ####


class _FixtureProvider:
  def __init__(self, *, capability: v1.CapabilityIdentity, result: Any | None, provider_id: str) -> None:
    self._capability = capability
    self._result = result
    self._descriptor = v1.ProviderDescriptor(
      provider_id=provider_id,
      provider_version='1.0.0',
      supported_capabilities=(capability,),
      provider_definition_schema_id=f'{provider_id}.definition.v1',
      dynamic_state_schema_id=f'{provider_id}.dynamic.v1',
      configuration_schema_id=f'{provider_id}.configuration.v1',
      supported_morphologies=('fixture',),
      deterministic=True,
    )
  ####

  @property
  def descriptor(self) -> v1.ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: Mapping[str, Any],
      configuration: Mapping[str, Any],
  ) -> _FixtureSession:
    return _FixtureSession(
      provider_id=self._descriptor.provider_id,
      provider_version=self._descriptor.provider_version,
      capability=self._capability,
      result=self._result,
    )
  ####


class FakeVisualOnlyProvider(_FixtureProvider):
  """A visual-only provider with no implied spectral capabilities."""

  def __init__(self) -> None:
    super().__init__(
      capability=v1.VISUAL_SECTIONED_TUBE_CAPABILITY,
      result=_load_result('visual_sectioned_tube_v1.json', v1.VisualSectionedTubeResult),
      provider_id='fixture.visual-only',
    )
  ####
####


class FakeSignatureOnlyProvider(_FixtureProvider):
  """A signature-only provider used for matrix and partial-result checks."""

  def __init__(self) -> None:
    super().__init__(
      capability=v1.SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      result=_load_result('spectral_signature_v1.json', v1.SpectralSignatureResult),
      provider_id='fixture.signature-only',
    )
  ####
####


class FakeRayTransferProvider(_FixtureProvider):
  """A fixture ray provider for hit/miss contract checks only."""

  def __init__(self) -> None:
    super().__init__(
      capability=v1.SPECTRAL_RAY_TRANSFER_CAPABILITY,
      result=_load_result('spectral_ray_transfer_v1.json', v1.VersionedSpectralRayTransferResult),
      provider_id='fixture.ray-transfer',
    )
  ####
####


class FakeFailureProvider(_FixtureProvider):
  """Advertises visual output but returns a snapshot with no evaluator."""

  def __init__(self) -> None:
    super().__init__(
      capability=v1.VISUAL_SECTIONED_TUBE_CAPABILITY,
      result=None,
      provider_id='fixture.descriptor-mismatch',
    )
  ####
####


__all__ = (
  'FakeFailureProvider',
  'FakeRayTransferProvider',
  'FakeSignatureOnlyProvider',
  'FakeVisualOnlyProvider',
)
