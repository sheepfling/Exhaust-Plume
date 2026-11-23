"""Versioned, frame-aware conservative handoff section contract."""

from __future__ import annotations

import json
from math import isclose, isfinite, sqrt
from typing import Any

from pydantic import Field, StrictBool, field_validator, model_validator

from exhaust_plume.contracts.common_v1 import ApiModel, QuaternionXyzw, Vector3
from exhaust_plume.contracts._validation import contains_boolean


def _rotate_vector(rotation_xyzw: QuaternionXyzw, vector: Vector3) -> Vector3:
  qx, qy, qz, qw = rotation_xyzw
  vx, vy, vz = vector
  cross_one = (qy * vz - qz * vy, qz * vx - qx * vz, qx * vy - qy * vx)
  cross_two = (
    qy * cross_one[2] - qz * cross_one[1],
    qz * cross_one[0] - qx * cross_one[2],
    qx * cross_one[1] - qy * cross_one[0],
  )
  return tuple(
    component + 2.0 * (qw * first + second)
    for component, first, second in zip(vector, cross_one, cross_two, strict=True)
  )  # type: ignore[return-value]
####


class HandoffPoseV1(ApiModel):
  """Pose coordinates with quaternion order ``(x, y, z, w)``."""

  translation_m: Vector3 = Field(min_length=3, max_length=3)
  rotation_xyzw: QuaternionXyzw = Field(min_length=4, max_length=4)

  @field_validator('translation_m', 'rotation_xyzw', mode='before')
  @classmethod
  def reject_boolean_pose_values(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('handoff pose values must not be booleans')
    return value
  ####

  @model_validator(mode='after')
  def validate_pose(self) -> 'HandoffPoseV1':
    if not all(isfinite(value) for value in (*self.translation_m, *self.rotation_xyzw)):
      raise ValueError('handoff pose values must be finite')
    if abs(sqrt(sum(value * value for value in self.rotation_xyzw)) - 1.0) > 1.0e-6:
      raise ValueError('rotation_xyzw must be unit length')
    return self
  ####
####


class HandoffFrameV1(ApiModel):
  """Frame identity and pose of that frame in its optional parent frame."""

  frame_id: str = Field(min_length=1)
  parent_frame_id: str | None = None
  pose_parent_from_frame: HandoffPoseV1

  @model_validator(mode='after')
  def validate_frame(self) -> 'HandoffFrameV1':
    if self.parent_frame_id == self.frame_id:
      raise ValueError('frame_id cannot be its own parent')
    return self
  ####
####


class HandoffSpeciesMassFlowV1(ApiModel):
  species_id: str = Field(min_length=1)
  mass_flow_kg_s: float = Field(ge=0.0)

  @field_validator('mass_flow_kg_s', mode='before')
  @classmethod
  def reject_boolean_mass_flow(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('species mass flow must not be a boolean')
    return value
  ####

  @field_validator('mass_flow_kg_s')
  @classmethod
  def validate_finite_flow(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('species mass flow must be finite')
    return value
  ####
####


class HandoffProvenanceV1(ApiModel):
  """Source identity retained from the producer of this section."""

  model_id: str = Field(min_length=1)
  model_version: str = Field(min_length=1)
  code_revision: str = Field(min_length=1)
  configuration_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
  asset_digests_sha256: tuple[str, ...] = ()
  producer_metadata: dict[str, Any] = Field(default_factory=dict)

  @field_validator('asset_digests_sha256')
  @classmethod
  def validate_asset_digests(cls, values: tuple[str, ...]) -> tuple[str, ...]:
    if any(len(value) != 64 or any(character not in '0123456789abcdef' for character in value) for value in values):
      raise ValueError('asset_digests_sha256 must contain lowercase SHA-256 digests')
    return values
  ####

  @field_validator('producer_metadata')
  @classmethod
  def validate_producer_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
    if any(not key.strip() for key in value):
      raise ValueError('producer_metadata keys must not be blank')
    try:
      json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as error:
      raise ValueError('producer_metadata must contain finite JSON-compatible values') from error
    return value
  ####
####


class HandoffApplicabilityV1(ApiModel):
  supported: StrictBool
  domain: dict[str, Any] = Field(default_factory=dict)
  violations: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validate_applicability(self) -> 'HandoffApplicabilityV1':
    if self.supported and self.violations:
      raise ValueError('supported applicability cannot contain violations')
    if not self.supported and not self.violations:
      raise ValueError('unsupported applicability must explain at least one violation')
    return self
  ####
####


class PlumeFluxSectionV1(ApiModel):
  """Canonical conservative section data for provider-to-provider handoff.

  ``section_pose.translation_m`` is the section centre. ``normal`` and all
  momentum vectors are expressed in ``frame.frame_id``. The section pose's
  local +x axis is the positive downstream normal; its local y-z plane defines
  the basis of the cross-section moment matrix. Total momentum is advective
  momentum plus pressure
  thrust, where pressure thrust is ``(pressure_Pa - ambient_pressure_Pa) *
  area_m2 * normal``. ``total_energy_flow_W`` is retained only for legacy
  interchange and is never treated as stagnation-enthalpy flux. The second
  moment matrix uses the oriented section's local transverse basis and is
  invariant under a rigid change of its containing frame.
  """

  time_s: float
  frame: HandoffFrameV1
  section_pose: HandoffPoseV1
  center_m: Vector3 = Field(min_length=3, max_length=3)
  normal: Vector3 = Field(min_length=3, max_length=3)
  area_m2: float = Field(gt=0.0)
  mass_flow_kg_s: float = Field(gt=0.0)
  momentum_flux_N: Vector3 = Field(min_length=3, max_length=3)
  advective_momentum_flux_N: Vector3 = Field(min_length=3, max_length=3)
  pressure_thrust_N: Vector3 = Field(min_length=3, max_length=3)
  stagnation_enthalpy_flux_W: float | None = Field(default=None, gt=0.0)
  total_energy_flow_W: float | None = Field(default=None, gt=0.0)
  species_mass_flows_kg_s: tuple[HandoffSpeciesMassFlowV1, ...] = Field(min_length=1)
  pressure_Pa: float = Field(gt=0.0)
  ambient_pressure_Pa: float = Field(gt=0.0)
  pressure_match_relative_residual: float = Field(ge=0.0)
  cross_section_second_moment_m2: tuple[tuple[float, float], tuple[float, float]]
  characteristic_radius_m: float | None = Field(default=None, gt=0.0)
  provenance: HandoffProvenanceV1
  applicability: HandoffApplicabilityV1
  uncertainty: dict[str, Any] = Field(default_factory=dict)

  @field_validator(
    'time_s',
    'center_m',
    'normal',
    'area_m2',
    'mass_flow_kg_s',
    'momentum_flux_N',
    'advective_momentum_flux_N',
    'pressure_thrust_N',
    'stagnation_enthalpy_flux_W',
    'total_energy_flow_W',
    'pressure_Pa',
    'ambient_pressure_Pa',
    'pressure_match_relative_residual',
    'cross_section_second_moment_m2',
    'characteristic_radius_m',
    mode='before',
  )
  @classmethod
  def reject_boolean_numeric_values(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('handoff numeric values must not be booleans')
    return value
  ####

  @field_validator('time_s', 'area_m2', 'mass_flow_kg_s', 'pressure_Pa', 'ambient_pressure_Pa', 'pressure_match_relative_residual')
  @classmethod
  def validate_finite_scalars(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('handoff scalar values must be finite')
    return value
  ####

  @field_validator('stagnation_enthalpy_flux_W', 'total_energy_flow_W', 'characteristic_radius_m')
  @classmethod
  def validate_optional_finite_scalars(cls, value: float | None) -> float | None:
    if value is not None and not isfinite(value):
      raise ValueError('optional handoff scalar values must be finite')
    return value
  ####

  @field_validator('uncertainty')
  @classmethod
  def validate_uncertainty_json(cls, value: dict[str, Any]) -> dict[str, Any]:
    if any(not key.strip() for key in value):
      raise ValueError('uncertainty keys must not be blank')
    try:
      json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as error:
      raise ValueError('uncertainty must contain finite JSON-compatible values') from error
    return value
  ####

  @model_validator(mode='after')
  def validate_section(self) -> 'PlumeFluxSectionV1':
    vectors = (
      self.center_m,
      self.normal,
      self.momentum_flux_N,
      self.advective_momentum_flux_N,
      self.pressure_thrust_N,
    )
    if any(not isfinite(value) for vector in vectors for value in vector):
      raise ValueError('handoff vectors must be finite')
    normal_norm = sqrt(sum(value * value for value in self.normal))
    if abs(normal_norm - 1.0) > 1.0e-8:
      raise ValueError('normal must be a unit vector')
    pose_normal = _rotate_vector(self.section_pose.rotation_xyzw, (1.0, 0.0, 0.0))
    if any(
      not isclose(value, pose_value, rel_tol=0.0, abs_tol=1.0e-8)
      for value, pose_value in zip(self.normal, pose_normal, strict=True)
    ):
      raise ValueError('normal must match the section pose local +x axis')
    if any(
      not isclose(center, pose_center, rel_tol=0.0, abs_tol=1.0e-12)
      for center, pose_center in zip(self.center_m, self.section_pose.translation_m, strict=True)
    ):
      raise ValueError('center_m must match section_pose.translation_m')
    if any(
      not isclose(total, advective + pressure, rel_tol=1.0e-10, abs_tol=1.0e-10)
      for total, advective, pressure in zip(
        self.momentum_flux_N,
        self.advective_momentum_flux_N,
        self.pressure_thrust_N,
        strict=True,
      )
    ):
      raise ValueError('momentum_flux_N must equal advective momentum plus pressure thrust')
    expected_pressure_thrust = tuple(
      (self.pressure_Pa - self.ambient_pressure_Pa) * self.area_m2 * value for value in self.normal
    )
    if any(
      not isclose(observed, expected, rel_tol=1.0e-10, abs_tol=1.0e-10)
      for observed, expected in zip(self.pressure_thrust_N, expected_pressure_thrust, strict=True)
    ):
      raise ValueError('pressure_thrust_N does not close against pressure, ambient, area, and normal')
    expected_residual = abs(self.pressure_Pa - self.ambient_pressure_Pa) / self.ambient_pressure_Pa
    if not isclose(self.pressure_match_relative_residual, expected_residual, rel_tol=1.0e-9, abs_tol=1.0e-12):
      raise ValueError('pressure_match_relative_residual does not match the pressure values')
    species_ids = tuple(item.species_id for item in self.species_mass_flows_kg_s)
    if len(species_ids) != len(set(species_ids)):
      raise ValueError('species_id values must be unique')
    if not isclose(
      sum(item.mass_flow_kg_s for item in self.species_mass_flows_kg_s),
      self.mass_flow_kg_s,
      rel_tol=1.0e-8,
      abs_tol=1.0e-12,
    ):
      raise ValueError('species mass flows must reconcile with total mass flow')
    moment = self.cross_section_second_moment_m2
    if any(not isfinite(value) for row in moment for value in row):
      raise ValueError('cross-section second moment must be finite')
    if abs(moment[0][1] - moment[1][0]) > 1.0e-12:
      raise ValueError('cross-section second moment must be symmetric')
    if moment[0][0] < -1.0e-12 or moment[1][1] < -1.0e-12:
      raise ValueError('cross-section second moment must be positive semidefinite')
    determinant = moment[0][0] * moment[1][1] - moment[0][1] * moment[1][0]
    if determinant < -1.0e-12:
      raise ValueError('cross-section second moment must be positive semidefinite')
    if self.stagnation_enthalpy_flux_W is None and self.total_energy_flow_W is None:
      raise ValueError('at least one explicitly named energy-flow quantity is required')
    return self
  ####

  @property
  def solver_handoff_ready(self) -> bool:
    """Whether the required stagnation-enthalpy flux is present."""

    return self.stagnation_enthalpy_flux_W is not None
  ####
####


__all__ = (
  'HandoffApplicabilityV1',
  'HandoffFrameV1',
  'HandoffPoseV1',
  'HandoffProvenanceV1',
  'HandoffSpeciesMassFlowV1',
  'PlumeFluxSectionV1',
  'transform_plume_flux_section_v1',
)


def _quaternion_multiply(
    left: QuaternionXyzw,
    right: QuaternionXyzw,
) -> QuaternionXyzw:
  lx, ly, lz, lw = left
  rx, ry, rz, rw = right
  return (
    lw * rx + lx * rw + ly * rz - lz * ry,
    lw * ry - lx * rz + ly * rw + lz * rx,
    lw * rz + lx * ry - ly * rx + lz * rw,
    lw * rw - lx * rx - ly * ry - lz * rz,
  )
####


def transform_plume_flux_section_v1(
    section: PlumeFluxSectionV1,
    *,
    target_frame: HandoffFrameV1,
    target_from_source: HandoffPoseV1,
) -> PlumeFluxSectionV1:
  """Express a section in another frame using ``target_from_source``.

  ``target_from_source`` maps coordinates from the section's current frame to
  ``target_frame.frame_id``. Positions receive rotation and translation;
  normals and momentum receive rotation only. The local section moment matrix
  is preserved because its basis moves with ``section_pose``.
  """

  if not isinstance(section, PlumeFluxSectionV1):
    raise TypeError('section must be a PlumeFluxSectionV1')
  if not isinstance(target_frame, HandoffFrameV1):
    raise TypeError('target_frame must be a HandoffFrameV1')
  if not isinstance(target_from_source, HandoffPoseV1):
    raise TypeError('target_from_source must be a HandoffPoseV1')
  translation = target_from_source.translation_m
  rotation = target_from_source.rotation_xyzw

  def transform_position(position: Vector3) -> Vector3:
    rotated = _rotate_vector(rotation, position)
    return tuple(value + offset for value, offset in zip(rotated, translation, strict=True))  # type: ignore[return-value]
  ####

  values = section.model_dump(mode='python')
  center = transform_position(section.center_m)
  section_rotation = _quaternion_multiply(rotation, section.section_pose.rotation_xyzw)
  values.update({
    'frame': target_frame,
    'center_m': center,
    'section_pose': HandoffPoseV1(
      translation_m=center,
      rotation_xyzw=section_rotation,
    ),
    'normal': _rotate_vector(rotation, section.normal),
    'momentum_flux_N': _rotate_vector(rotation, section.momentum_flux_N),
    'advective_momentum_flux_N': _rotate_vector(rotation, section.advective_momentum_flux_N),
    'pressure_thrust_N': _rotate_vector(rotation, section.pressure_thrust_N),
  })
  return PlumeFluxSectionV1.model_validate(values)
####
