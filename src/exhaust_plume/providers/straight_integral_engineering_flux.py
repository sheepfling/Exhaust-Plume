"""Source-bound engineering-flux evaluator for the straight-integral lane."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import pi, sqrt

from exhaust_plume.contracts.capability import ENGINEERING_FLUX_SECTION_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ProductClaims,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SnapshotMetadata,
  TimeModel,
  canonical_digest,
)
from exhaust_plume.contracts.engineering_flux_v1 import (
  EngineeringFluxSectionRequest,
  EngineeringFluxSectionResult,
  EngineeringFluxSectionSampleV1,
)
from exhaust_plume.contracts.errors import ProductOutsideApplicabilityError
from exhaust_plume.contracts.handoff_v1 import (
  HandoffApplicabilityV1,
  HandoffFrameV1,
  HandoffPoseV1,
  HandoffProvenanceV1,
  HandoffSpeciesMassFlowV1,
  PlumeFluxSectionV1,
)
from exhaust_plume.models.integral.straight import IntegralStraightResult, IntegralStraightState


@dataclass(frozen=True, slots=True)
class _FluxValues:
  mass_flow_kg_s: float
  momentum_flux_N: float
  stagnation_enthalpy_flux_W: float
  pressure_Pa: float
  area_m2: float
  species_mass_flows_kg_s: tuple[tuple[str, float], ...]


class StraightIntegralEngineeringFluxEvaluator:
  """Expose only conservative states retained by one straight-integral result.

  The solver's axial coordinate is the centerline arc length from its native
  handoff origin. Non-native stations require explicit request interpolation;
  no extrapolation or geometry-derived flow values are produced.
  """

  def __init__(
    self,
    *,
    result: IntegralStraightResult,
    frame_id: str,
    centerline_reference_id: str,
    provider_id: str,
    provider_version: str,
    code_revision: str,
    configuration_digest_sha256: str,
    result_definition_digest_sha256: str,
  ) -> None:
    if not isinstance(result, IntegralStraightResult):
      raise TypeError('result must be IntegralStraightResult')
    if not frame_id or not centerline_reference_id or not provider_id or not provider_version:
      raise ValueError('frame and provider identities must not be empty')
    if not code_revision:
      raise ValueError('code_revision must be explicit before exposing engineering flux')
    for name, value in (
      ('configuration_digest_sha256', configuration_digest_sha256),
      ('result_definition_digest_sha256', result_definition_digest_sha256),
    ):
      if len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
    stations = tuple(state.x_m for state in result.states)
    if any(later <= earlier for earlier, later in zip(stations, stations[1:])):
      raise ValueError('straight-integral state stations must be strictly increasing')
    self._result = result
    self._frame_id = frame_id
    self._centerline_reference_id = centerline_reference_id
    self._provider_id = provider_id
    self._provider_version = provider_version
    self._code_revision = code_revision
    self._configuration_digest_sha256 = configuration_digest_sha256
    self._result_definition_digest_sha256 = result_definition_digest_sha256
    self._stations_m = stations
    self._state_values = tuple(self._values_from_state(state) for state in result.states)
  ####

  @staticmethod
  def _values_from_state(state: IntegralStraightState) -> _FluxValues:
    return _FluxValues(
      mass_flow_kg_s=state.mass_flow_rate_kg_s,
      momentum_flux_N=state.momentum_flux_N,
      stagnation_enthalpy_flux_W=state.total_enthalpy_flux_W,
      pressure_Pa=state.pressure_Pa,
      area_m2=pi * state.radius_m * state.radius_m,
      species_mass_flows_kg_s=tuple(
        (name, state.mass_flow_rate_kg_s * fraction)
        for name, fraction in state.species_mass_fractions
      ),
    )
  ####

  @staticmethod
  def _interpolate(
    left: _FluxValues,
    right: _FluxValues,
    fraction: float,
  ) -> _FluxValues:
    def lerp(start: float, end: float) -> float:
      return start + fraction * (end - start)
    ####

    left_species = dict(left.species_mass_flows_kg_s)
    right_species = dict(right.species_mass_flows_kg_s)
    species_ids = tuple(sorted(set(left_species) | set(right_species)))
    return _FluxValues(
      mass_flow_kg_s=lerp(left.mass_flow_kg_s, right.mass_flow_kg_s),
      momentum_flux_N=lerp(left.momentum_flux_N, right.momentum_flux_N),
      stagnation_enthalpy_flux_W=lerp(
        left.stagnation_enthalpy_flux_W,
        right.stagnation_enthalpy_flux_W,
      ),
      pressure_Pa=lerp(left.pressure_Pa, right.pressure_Pa),
      area_m2=lerp(left.area_m2, right.area_m2),
      species_mass_flows_kg_s=tuple(
        (name, lerp(left_species.get(name, 0.0), right_species.get(name, 0.0)))
        for name in species_ids
      ),
    )
  ####

  def _sample_values(
    self,
    station_m: float,
    *,
    allow_interpolation: bool,
  ) -> tuple[_FluxValues | None, str | None, str | None]:
    index = bisect_left(self._stations_m, station_m)
    if index < len(self._stations_m) and self._stations_m[index] == station_m:
      values = self._state_values[index]
      if not values.species_mass_flows_kg_s:
        return None, None, 'native source state does not retain species mass fractions'
      return values, 'native', None
    ####
    if station_m < self._stations_m[0] or station_m > self._stations_m[-1]:
      return None, None, 'requested station lies outside the retained straight-integral domain'
    ####
    if not allow_interpolation:
      return None, None, 'requested station is not a native provider station and interpolation was not requested'
    ####
    if index == 0 or index >= len(self._stations_m):
      return None, None, 'requested station cannot be bracketed by retained provider states'
    ####
    left_values = self._state_values[index - 1]
    right_values = self._state_values[index]
    if not left_values.species_mass_flows_kg_s or not right_values.species_mass_flows_kg_s:
      return None, None, 'bracketing source states do not retain species mass fractions'
    ####
    left_station = self._stations_m[index - 1]
    right_station = self._stations_m[index]
    weight = (station_m - left_station) / (right_station - left_station)
    return self._interpolate(left_values, right_values, weight), 'provider-interpolated', None
  ####

  def _section(
    self,
    values: _FluxValues,
    *,
    station_m: float,
    snapshot: SnapshotMetadata,
    sampling_method: str,
  ) -> PlumeFluxSectionV1:
    position = (station_m, 0.0, 0.0)
    normal = (1.0, 0.0, 0.0)
    radius_squared = values.area_m2 / pi
    second_moment = radius_squared / 4.0
    frame = HandoffFrameV1(
      frame_id=self._frame_id,
      parent_frame_id=None,
      pose_parent_from_frame=HandoffPoseV1(
        translation_m=(0.0, 0.0, 0.0),
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
    )
    source_provenance = HandoffProvenanceV1(
      model_id='straight-integral-top-hat',
      model_version=self._provider_version,
      code_revision=self._code_revision,
      configuration_sha256=self._configuration_digest_sha256,
      producer_metadata={
        'provider_id': self._provider_id,
        'result_definition_digest_sha256': self._result_definition_digest_sha256,
        'sampling_method': sampling_method,
        'solver_termination_reason': self._result.termination_reason.value,
        'solver_termination_is_physical': self._result.termination_is_physical,
      },
    )
    return PlumeFluxSectionV1(
      time_s=snapshot.time_s,
      frame=frame,
      section_pose=HandoffPoseV1(
        translation_m=position,
        rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      center_m=position,
      normal=normal,
      area_m2=values.area_m2,
      mass_flow_kg_s=values.mass_flow_kg_s,
      momentum_flux_N=(values.momentum_flux_N, 0.0, 0.0),
      advective_momentum_flux_N=(values.momentum_flux_N, 0.0, 0.0),
      pressure_thrust_N=(0.0, 0.0, 0.0),
      stagnation_enthalpy_flux_W=values.stagnation_enthalpy_flux_W,
      total_energy_flow_W=None,
      species_mass_flows_kg_s=tuple(
        HandoffSpeciesMassFlowV1(species_id=name, mass_flow_kg_s=flow)
        for name, flow in values.species_mass_flows_kg_s
      ),
      pressure_Pa=values.pressure_Pa,
      ambient_pressure_Pa=values.pressure_Pa,
      pressure_match_relative_residual=0.0,
      cross_section_second_moment_m2=(
        (second_moment, 0.0),
        (0.0, second_moment),
      ),
      characteristic_radius_m=sqrt(radius_squared),
      provenance=source_provenance,
      applicability=HandoffApplicabilityV1(
        supported=True,
        domain={
          'fidelity_lane': 'straight-integral-v1',
          'station_range_m': [self._stations_m[0], self._stations_m[-1]],
          'sampled_station_m': station_m,
          'sampling_method': sampling_method,
        },
      ),
      uncertainty={},
    )
  ####

  def evaluate(
    self,
    request: EngineeringFluxSectionRequest,
    snapshot: SnapshotMetadata,
  ) -> EngineeringFluxSectionResult:
    if not isinstance(request, EngineeringFluxSectionRequest):
      raise TypeError('request must be EngineeringFluxSectionRequest')
    if not isinstance(snapshot, SnapshotMetadata):
      raise TypeError('snapshot must be SnapshotMetadata')
    if request.output_frame_id != self._frame_id:
      raise ProductOutsideApplicabilityError(
        f'straight-integral flux provider supports frame {self._frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    if request.centerline_reference_id != self._centerline_reference_id:
      raise ProductOutsideApplicabilityError(
        'request centerline reference does not identify the retained straight-integral centerline'
      )

    samples = []
    for station_m in request.centerline_arclength_m:
      values, sampling_method, failure_message = self._sample_values(
        station_m,
        allow_interpolation=request.allow_interpolation,
      )
      if failure_message is not None or values is None or sampling_method is None:
        if not request.allow_partial_results:
          raise ProductOutsideApplicabilityError(failure_message or 'requested flux section is unavailable')
        samples.append(EngineeringFluxSectionSampleV1(
          station_arclength_m=station_m,
          centerline_position_m=None,
          centerline_tangent=None,
          sampling_method=None,
          status=SampleStatus(
            code=SampleStatusCode.OUTSIDE_APPLICABILITY,
            message=failure_message or 'requested flux section is unavailable',
            retryable=False,
          ),
          section=None,
        ))
        continue
      ####
      section = self._section(
        values,
        station_m=station_m,
        snapshot=snapshot,
        sampling_method=sampling_method,
      )
      samples.append(EngineeringFluxSectionSampleV1(
        station_arclength_m=station_m,
        centerline_position_m=(station_m, 0.0, 0.0),
        centerline_tangent=(1.0, 0.0, 0.0),
        sampling_method=sampling_method,
        status=SampleStatus(code=SampleStatusCode.OK),
        section=section,
      ))
    ####

    failed_messages = tuple(dict.fromkeys(
      sample.status.message
      for sample in samples
      if sample.status.message is not None
    ))
    interpolated = any(sample.sampling_method == 'provider-interpolated' for sample in samples)
    if failed_messages and any(sample.status.code is SampleStatusCode.OK for sample in samples):
      applicability_status = ApplicabilityStatus.MARGINAL
    elif failed_messages:
      applicability_status = ApplicabilityStatus.OUTSIDE
    elif interpolated:
      applicability_status = ApplicabilityStatus.MARGINAL
    else:
      applicability_status = ApplicabilityStatus.INSIDE
    ####
    request_digest = canonical_digest(request)
    result_identity = canonical_digest({
      'capability_id': ENGINEERING_FLUX_SECTION_CAPABILITY.wire_id,
      'snapshot_id': snapshot.snapshot_id,
      'request_digest_sha256': request_digest,
      'configuration_digest_sha256': self._configuration_digest_sha256,
      'result_definition_digest_sha256': self._result_definition_digest_sha256,
    })
    result_metadata = ResultMetadata(
      capability=ENGINEERING_FLUX_SECTION_CAPABILITY,
      result_id=f'engineering-flux:{result_identity}',
      request_digest_sha256=request_digest,
      snapshot=snapshot,
      output_frame_id=request.output_frame_id,
      claims=ProductClaims(
        geometry=GeometryClaim.ENGINEERING_APPROXIMATE,
        radiation=RadiationClaim.NOT_APPLICABLE,
        time_model=TimeModel.STEADY,
        derivation=Derivation.ADAPTED,
        consistency=ConsistencyLevel.CO_GENERATED,
      ),
      applicability=ApplicabilityReport(
        status=applicability_status,
        reasons=failed_messages + (('provider interpolation was explicitly requested',) if interpolated else ()),
      ),
      provenance=ResultProvenance(
        model_lineage_id=canonical_digest({
          'provider_result_identity': result_identity,
          'source_result_definition_digest_sha256': self._result_definition_digest_sha256,
        }),
        provider_id=self._provider_id,
        provider_version=self._provider_version,
        configuration_digest_sha256=self._configuration_digest_sha256,
        metadata={
          'centerline_reference_id': self._centerline_reference_id,
          'fidelity_lane': 'straight-integral-v1',
        },
      ),
      warnings=(
        'straight-integral top-hat flux sections are engineering-approximate and have not passed provider measurement validation',
      ),
    )
    return EngineeringFluxSectionResult(
      metadata=result_metadata,
      request=request,
      samples=tuple(samples),
    )
  ####
####


__all__ = ('StraightIntegralEngineeringFluxEvaluator',)
