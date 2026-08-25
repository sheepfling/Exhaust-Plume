# Straight and Washed Provider Design

## Straight provider

### Inputs

- canonical `PlumeFluxSection`;
- ambient thermodynamic state;
- calorically perfect gas/mixture model;
- finite domain and entrainment configuration.

### Outputs

Initially advertise:

```text
plume.visual.sectioned-tube@1
plume.engineering.flux-section@1
```

### Governing baseline

The landed straight continuation conserves momentum, imports ambient mass and enthalpy, keeps pressure matched to ambient, and reconstructs density/area/radius.

The provider PR must not alter that kernel except for defects exposed by exact tests.

## Washed provider

### Provider-specific objects

```text
WashedIntegralDefinition
  source_frame
  characteristic_source_diameter_m
  default_support_definition

WashedIntegralConfiguration
  W1 entrainment seed
  numerical tolerances
  termination thresholds
  ambient-field model specification

WashedIntegralOperatingState
  canonical PlumeFluxSection
  background ambient state
  optional rotor thrust/torque/pose
  time_s
```

The in-process API may accept constructed field objects through a private factory, but serialized sidecar input must use explicit model specifications.

### Internal flow

```text
canonical flux section
      -> CurvedPlumeSource adapter
      -> AmbientStateField builder
      -> solveCurvedPlume
      -> CurvedPlumeResult
      -> canonical SectionedTubePayload
      -> canonical result envelope
```

### W1 seed

```text
alpha_j                          0.07
initial development fraction    1/3
development length              4.6 source diameters
combination exponent            2
forced crossflow coefficient    0
ambient turbulence coefficient  0
beta_M                           1
gamma_E                          1
```

These values are reproducibility seeds, not validation claims.

### Geometry/support

The first physical field is top-hat, so the honest default support is `INTEGRAL_TOP_HAT_BOUNDARY`. Use `ENCLOSED_EXHAUST_MASS_FRACTION=0.95` only after a profile reconstruction actually defines that fraction.

### Termination

Report separately:

- equilibrium reached;
- passive-cloud handoff requested;
- slenderness/model-validity failure;
- spatial domain limit;
- numerical failure.

Use the selected numerical guards from the final decision register.

### Conformance

The provider advertises no optical or signature capability. Temperature and exhaust fraction may appear as visual feature channels but are not radiance or emissivity.
