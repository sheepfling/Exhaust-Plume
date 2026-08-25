# `WashedIntegralPlumeProvider` specification

## Purpose

Expose the landed conservative curved-plume kernel as the first live rotor-washed visual/engineering provider.

## W1 scope

Included:

- steady, pressure-matched source;
- non-Boussinesq ideal-gas reconstruction;
- circular top-hat section;
- mass, vector momentum, total energy, and exhaust-tracer conservation;
- uniform/composite ambient velocity fields;
- hover actuator-disk downwash and optional torque-derived swirl;
- hydrostatic buoyancy where its assumptions hold;
- rotation-minimizing section frames;
- structured equilibrium, slenderness, numerical-failure, and domain termination.

Deferred:

- forward-flight/free-vortex wake fidelity;
- slot/elliptical evolution;
- wall attachment or ground effect;
- multiple plume merger;
- passive-cloud handoff;
- chemistry, particles, molecular radiation, and resolved optical transfer.

## Canonical entrainment closure

Use one implementation only. The W1 shear contribution is:

\[
E_s=\rho_a P_e\alpha_j f_{\mathrm{dev}} C_M U_{\parallel},
\]

not a hidden duplicate with a different density law. The geometric-mean-density form may remain only as an explicitly named legacy/experimental closure if required for regression migration.

For a circular top-hat section:

\[
P_e=2\pi b.
\]

The development law is:

\[
f_{\mathrm{dev}}=f_0+(1-f_0)\left(1-e^{-s/L_{\mathrm{dev}}}\right).
\]

Forced crossflow remains disabled by default until calibrated:

\[
E_f=2b C_f\rho_a U_{\perp},\qquad C_f=0\ \text{for W1 stock defaults}.
\]

Stock exploratory seeds:

```text
alpha_j                         0.07
f0                              1/3
L_dev                           4.6 source diameters
combination exponent            2
forced crossflow coefficient    0
ambient turbulence coefficient  0
```

## Provider lifecycle

```text
WashedIntegralPlumeProvider
  -> WashedIntegralPlumeSession
      -> immutable snapshot
          -> visual sectioned tube
          -> engineering flux sections
```

Static definition/configuration should contain solver topology and closure choices. Operating state should contain time-varying source/ambient/rotor quantities. Exact serialized field names are finalized under PR-B; solver-private classes remain internal.

## Canonical adapters

Add under `exhaust_plume.api.adapters`:

```text
sectioned_tube_payload_from_curved_result(...)
flux_section_payload_from_curved_result(...)
```

The adapters must:

- use the landed rotation-minimizing frames;
- preserve strict arc-length ordering;
- emit explicit support definition;
- include only measured/solved feature channels;
- report termination and conservation diagnostics in metadata;
- never emit radiance, opacity, emissivity, or spectral claims.

## Termination defaults

```text
pressure-match tolerance        0.05
exhaust fraction                1e-3
ambient temperature difference  1 K
relative speed                  0.5 m/s
persistence                     5 source diameters
slenderness warning             kappa*b >= 0.10
slenderness termination         kappa*b >= 0.25
maximum arc length              100 source diameters
maximum integrator step         0.25 source diameters
default sections                256
maximum sections                2048
```

## Acceptance suite

1. Zero crossflow agrees with `StraightIntegralPlumeProvider` within declared numerical tolerance.
2. Full rigid transformation rotates/translates geometry and vectors without changing scalar histories.
3. Torque sign reversal mirrors lateral motion and preserves axial histories.
4. Frames remain orthonormal, right-handed, and rotation-minimizing through straight/curved transitions.
5. Mass, momentum, energy, and tracer residuals pass.
6. Slenderness warning/termination is exercised.
7. Pressure mismatch is rejected before integration.
8. Invalid ambient or rotor configuration produces structured errors.
9. Repeated snapshot reads are deterministic.
10. Only visual and engineering capabilities are advertised.
