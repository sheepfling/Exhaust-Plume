# Provider Contracts v1

## 1. Stable lifecycle contracts

```python
DefinitionT = TypeVar('DefinitionT')
ConfigurationT = TypeVar('ConfigurationT')
OperatingStateT = TypeVar('OperatingStateT')


class PlumeProvider(Protocol[DefinitionT, ConfigurationT, OperatingStateT]):
  @property
  def descriptor(self) -> PlumeProviderDescriptor:
    ...
  ####

  def create_session(
      self,
      definition: DefinitionT,
      configuration: ConfigurationT,
  ) -> PlumeSession[OperatingStateT]:
    ...
  ####
####


class PlumeSession(Protocol[OperatingStateT]):
  def snapshot(self, operating_state: OperatingStateT) -> PlumeSnapshot:
    ...
  ####

  def close(self) -> None:
    ...
  ####
####
```

## 2. Snapshot capability lookup

Use explicit capability IDs plus typed capability objects.

```python
class PlumeSnapshot:
  descriptor: PlumeProviderDescriptor
  termination: TerminationReport | None
  provenance: PlumeProvenance

  def get_capability(
      self,
      capability_id: CapabilityId,
      major_version: int,
  ) -> PlumeCapability:
    ...
  ####
####
```

Unsupported capability requests raise `UnsupportedCapabilityError`. A major
version mismatch raises `CapabilityVersionMismatchError`.

## 3. Descriptor

```python
@dataclass(frozen=True)
class PlumeProviderDescriptor:
  provider_id: str
  provider_version: str
  core_contract_major_version: int
  capability_versions: Mapping[CapabilityId, int]
  definition_schema_id: str
  configuration_schema_id: str
  operating_state_schema_id: str
  morphology: PlumeMorphology
  fidelity: ProviderFidelity
  execution: ProviderExecutionProfile
  applicability: ProviderApplicability
####
```

## 4. Fidelity metadata

```python
@dataclass(frozen=True)
class ProviderFidelity:
  geometry_model: str
  spatial_dimensionality: str
  temporal_model: str
  flow_model: str
  mixing_model: str
  thermochemistry_model: str
  radiation_model: str
  environmental_coupling: str
  validation_level: str
####
```

## 5. Execution profile

```python
@dataclass(frozen=True)
class ProviderExecutionProfile:
  time_access: TimeAccessMode
  concurrency: ConcurrencyMode
  deterministic: bool
  supports_direction_batching: bool
  maximum_direction_batch_size: int | None
  checkpointable: bool
  preferred_device: str
  snapshot_retention: SnapshotRetention
####
```

A GPU session may declare `MONOTONIC_FORWARD` and
`UNTIL_NEXT_SNAPSHOT`; a table or analytical provider will normally declare
`RANDOM_ACCESS` and `INDEPENDENT`.

## 6. Applicability

Applicability must be queryable before expensive execution when practical.

Possible bounds:

```text
time
Mach
pressure ratio
altitude/ambient pressure
wavelength
view direction/angular region
observer distance for unresolved approximation
spatial domain
supported propellant/species family
```

No silent extrapolation is allowed.

## 7. Termination

Spatial providers report structured termination separately from snapshot
validity.

Recommended reasons:

```text
NO_PRESSURE_MISMATCH
WEAK_WAVE_CUTOFF
PRESSURE_OSCILLATION_DECAYED
MIXING_LAYER_REACHED_AXIS
CORE_BECAME_SUBSONIC
AMBIENT_EQUILIBRIUM
MACH_DISK_REQUIRED
NOZZLE_SEPARATION_NOT_MODELED
SPATIAL_DOMAIN_LIMIT
TEMPORAL_DOMAIN_LIMIT
REQUESTED_CONSTRUCTION_LIMIT
PROVIDER_FAILURE
```

The report contains `is_physical` so safety/domain truncation is never confused
with a predicted plume endpoint.

## 8. Error taxonomy

```text
UnsupportedCapabilityError
CapabilityVersionMismatchError
ProviderConfigurationError
OperatingStateDomainError
SpectralDomainError
AngularDomainError
TemporalDomainError
SpatialDomainError
ContractViolationError
SnapshotInvalidatedError
ProviderClosedError
```

Physical out-of-model conditions should normally be structured domain/status
results rather than generic numerical exceptions.
