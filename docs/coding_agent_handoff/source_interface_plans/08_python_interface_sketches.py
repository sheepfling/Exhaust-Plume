from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar, cast

import numpy as np
from numpy.typing import NDArray


Float64Array = NDArray[np.float64]


class CapabilityId(StrEnum):
    AXISYMMETRIC_ZONE_FIELD = "axisymmetric-zone-field"
    SPATIAL_SUPPORT = "spatial-support"
    PROJECTED_AREA = "projected-area"
    DIRECTIONAL_SPECTRAL_INTENSITY = "directional-spectral-intensity"
    SPECTRAL_RAY_TRANSFER = "spectral-ray-transfer"
    OPTICAL_MEDIUM = "optical-medium"
    SCENE_RADIANCE_RENDERER = "scene-radiance-renderer"
####


class TimeAccessMode(StrEnum):
    RANDOM_ACCESS = "random-access"
    MONOTONIC_FORWARD = "monotonic-forward"
####


class ConcurrencyMode(StrEnum):
    REENTRANT = "reentrant"
    SESSION_ISOLATED = "session-isolated"
    SERIALIZED = "serialized"
####


class SnapshotRetention(StrEnum):
    INDEPENDENT = "independent"
    UNTIL_SESSION_CLOSE = "until-session-close"
    UNTIL_NEXT_SNAPSHOT = "until-next-snapshot"
####


class TerminationReason(StrEnum):
    REQUESTED_CONSTRUCTION_LIMIT = "requested-construction-limit"
    WEAK_WAVE_CUTOFF = "weak-wave-cutoff"
    AMBIENT_EQUILIBRIUM = "ambient-equilibrium"
    SPATIAL_DOMAIN_LIMIT = "spatial-domain-limit"
    TEMPORAL_DOMAIN_LIMIT = "temporal-domain-limit"
    PROVIDER_FAILURE = "provider-failure"
####


@dataclass(frozen=True)
class ProviderExecutionProfile:
    time_access: TimeAccessMode
    concurrency: ConcurrencyMode
    deterministic: bool
    supports_direction_batching: bool
    maximum_direction_batch_size: int | None
    checkpointable: bool
    snapshot_retention: SnapshotRetention
    preferred_device: str = "cpu"
####


@dataclass(frozen=True)
class ProviderFidelity:
    geometry_model: str
    temporal_model: str
    flow_model: str
    thermochemistry_model: str
    radiation_model: str
    environmental_coupling: str
####


@dataclass(frozen=True)
class PlumeProviderDescriptor:
    provider_id: str
    provider_version: str
    core_contract_major_version: int
    capability_versions: Mapping[CapabilityId, int]
    definition_schema_id: str
    configuration_schema_id: str
    operating_state_schema_id: str
    execution: ProviderExecutionProfile
    fidelity: ProviderFidelity
####


@dataclass(frozen=True)
class TerminationReport:
    reason: TerminationReason
    is_physical: bool
    axial_extent_m: float | None = None
    pressure_residual_fraction: float | None = None
    temperature_residual_fraction: float | None = None
    last_active_wave_type: str | None = None
    warnings: tuple[str, ...] = ()
####


@dataclass(frozen=True)
class BulkNozzleExitState:
    static_pressure_pa: float
    static_temperature_k: float
    static_density_kg_m3: float
    velocity_plume_m_s: tuple[float, float, float]
    ratio_of_specific_heats: float
    species_mass_fraction: tuple[tuple[str, float], ...] = ()
####


@dataclass(frozen=True)
class UniformAmbientState:
    static_pressure_pa: float
    static_temperature_k: float
    static_density_kg_m3: float
    velocity_plume_m_s: tuple[float, float, float]
    species_mass_fraction: tuple[tuple[str, float], ...] = ()
####


@dataclass(frozen=True)
class BulkNozzleOperatingState:
    time_s: float
    nozzle_exit: BulkNozzleExitState
    ambient: UniformAmbientState
####


@dataclass(frozen=True)
class SpectralGrid:
    wavelength_m: Float64Array
####


@dataclass(frozen=True)
class DirectionalSpectralIntensityQuery:
    spectrum: SpectralGrid
    source_to_observer_direction_plume: Float64Array
####


@dataclass(frozen=True)
class DirectionalSpectralIntensityResult:
    spectrum: SpectralGrid
    source_to_observer_direction_plume: Float64Array
    spectral_radiant_intensity_w_sr_m: Float64Array
    quality_flags: tuple[str, ...] = ()
####


@dataclass(frozen=True)
class SpectralRayQuery:
    spectrum: SpectralGrid
    observer_origin_plume_m: Float64Array
    observer_to_scene_direction_plume: Float64Array
    maximum_distance_m: Float64Array
####


@dataclass(frozen=True)
class SpectralRayTransferResult:
    spectrum: SpectralGrid
    source_spectral_radiance_w_m2_sr_m: Float64Array
    background_transmittance: Float64Array
    quality_flags: tuple[str, ...] = ()
####


@dataclass(frozen=True)
class AxisymmetricZone:
    zone_id: str
    polygon_xr_m: Float64Array
    static_pressure_pa: float
    static_temperature_k: float
    static_density_kg_m3: float
    mach: float | None
    phase: str
    provider_metadata: Mapping[str, object] = field(default_factory=dict)
####


@dataclass(frozen=True)
class AxisymmetricZoneField:
    zones: tuple[AxisymmetricZone, ...]
    axis_origin_plume_m: Float64Array
    axis_direction_plume: Float64Array
####


class UnsupportedCapabilityError(RuntimeError):
    pass
####


class CapabilityVersionMismatchError(RuntimeError):
    pass
####


class ContractViolationError(RuntimeError):
    pass
####


class SnapshotInvalidatedError(RuntimeError):
    pass
####


class PlumeCapability(ABC):
    capability_id: CapabilityId
    capability_major_version: int
####


class DirectionalSpectralIntensityCapability(PlumeCapability):
    capability_id = CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY
    capability_major_version = 1

    @abstractmethod
    def evaluate_directional_spectral_intensity(
        self,
        query: DirectionalSpectralIntensityQuery,
    ) -> DirectionalSpectralIntensityResult:
        raise NotImplementedError
    ####
####


class SpectralRayTransferCapability(PlumeCapability):
    capability_id = CapabilityId.SPECTRAL_RAY_TRANSFER
    capability_major_version = 1

    @abstractmethod
    def evaluate_spectral_ray_transfer(
        self,
        query: SpectralRayQuery,
    ) -> SpectralRayTransferResult:
        raise NotImplementedError
    ####
####


CapabilityT = TypeVar("CapabilityT", bound=PlumeCapability)


@dataclass(frozen=True)
class PlumeSnapshot:
    descriptor: PlumeProviderDescriptor
    termination: TerminationReport | None
    _capabilities: Mapping[CapabilityId, PlumeCapability] = field(repr=False)

    def __post_init__(self) -> None:
        capability_map = dict(self._capabilities)
        declared = frozenset(self.descriptor.capability_versions)
        actual = frozenset(capability_map)
        if declared != actual:
            raise ContractViolationError(
                f"Descriptor capabilities {declared!r} do not match snapshot capabilities {actual!r}."
            )
        object.__setattr__(self, "_capabilities", MappingProxyType(capability_map))
    ####

    def require(self, capability_type: type[CapabilityT]) -> CapabilityT:
        capability_id = capability_type.capability_id
        capability = self._capabilities.get(capability_id)
        if capability is None:
            raise UnsupportedCapabilityError(capability_id)
        if capability.capability_major_version != capability_type.capability_major_version:
            raise CapabilityVersionMismatchError(capability_id)
        if not isinstance(capability, capability_type):
            raise ContractViolationError(capability_id)
        return cast(CapabilityT, capability)
    ####
####


DefinitionT = TypeVar("DefinitionT")
ConfigurationT = TypeVar("ConfigurationT")
OperatingStateT = TypeVar("OperatingStateT")


class PlumeSession(Protocol, Generic[OperatingStateT]):
    @property
    def descriptor(self) -> PlumeProviderDescriptor:
        ...
    ####

    def snapshot(self, state: OperatingStateT) -> PlumeSnapshot:
        ...
    ####

    def close(self) -> None:
        ...
    ####
####


class PlumeProvider(
    Protocol,
    Generic[DefinitionT, ConfigurationT, OperatingStateT],
):
    @property
    def descriptor(self) -> PlumeProviderDescriptor:
        ...
    ####

    def create_session(
        self,
        *,
        definition: DefinitionT,
        configuration: ConfigurationT,
    ) -> PlumeSession[OperatingStateT]:
        ...
    ####
####


@dataclass(frozen=True)
class DirectionalSpectralSourceQuery:
    epoch_tai_ns: int
    wavelength_m: Float64Array
    source_to_observer_direction_source: Float64Array
####


@dataclass(frozen=True)
class DirectionalSpectralSourceResult:
    source_id: str
    source_model_id: str
    source_model_version: str
    wavelength_m: Float64Array
    source_to_observer_direction_source: Float64Array
    spectral_radiant_intensity_w_sr_m: Float64Array
    provenance_id: str
    quality_flags: tuple[str, ...] = ()
####


class DirectionalSpectralSource(Protocol):
    @property
    def source_id(self) -> str:
        ...
    ####

    @property
    def model_id(self) -> str:
        ...
    ####

    @property
    def model_version(self) -> str:
        ...
    ####

    def evaluate(
        self,
        query: DirectionalSpectralSourceQuery,
    ) -> DirectionalSpectralSourceResult:
        ...
    ####
####


@dataclass(frozen=True)
class SourcePose:
    epoch_tai_ns: int
    position_gcrs_m: tuple[float, float, float]
    quaternion_source_from_gcrs_wxyz: tuple[float, float, float, float]
####


class SourcePoseProvider(Protocol):
    def pose_at(self, epoch_tai_ns: int) -> SourcePose:
        ...
    ####
####


OperatingStateProviderT = TypeVar("OperatingStateProviderT")


class PlumeOperatingStateProvider(Protocol, Generic[OperatingStateT]):
    def state_at(self, epoch_tai_ns: int) -> OperatingStateT:
        ...
    ####
####
