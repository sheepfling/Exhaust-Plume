# Generic Plume Provider Interface — Unified Version

The authoritative merged interface architecture is now split across:

- [`00_unified_plume_architecture.md`](00_unified_plume_architecture.md)
- [`28_consumer_profiles_and_query_contracts.md`](28_consumer_profiles_and_query_contracts.md)
- [`29_provider_taxonomy_and_composition.md`](29_provider_taxonomy_and_composition.md)
- [`30_provider_contracts_v1.md`](30_provider_contracts_v1.md)
- [`31_unified_conformance_and_testing.md`](31_unified_conformance_and_testing.md)
- [`32_merged_implementation_roadmap.md`](32_merged_implementation_roadmap.md)

## Stable summary

The shock-cell solver is one provider, not the universal plume API.

There are two primary consumer views:

```text
SIGNATURE VIEW
  -> directional spectral radiant intensity

SPATIAL / PHYSICAL VIEW
  -> support, geometry, fields, optical medium, or ray transfer
```

A provider may support either or both. Geometry may be used internally without
being exposed.

The following are orthogonal metadata, not interface hierarchies:

```text
morphology: straight / curved / rotor-washed / general-3d
flow fidelity: empirical / analytical / integral / CFD
radiation fidelity: none / gray / band / line-by-line / non-LTE
execution: CPU / GPU / external, random-access / monotonic, etc.
```

The stable lifecycle is:

```text
provider-specific definition/configuration
  -> PlumeSession
      -> snapshot(provider-specific operating state)
          -> PlumeSnapshot
              -> explicit capability registry
```

The unresolved intrinsic source quantity is

\[
J_\lambda(t,\hat{\mathbf d})
\quad [\mathrm{W\,sr^{-1}\,m^{-1}}],
\]

while resolved ray transfer is

\[
L_{\lambda,out}
=L_{\lambda,source}+T_\lambda L_{\lambda,background}.
\]

A rich spatial/ray provider may derive the unresolved source by

\[
J_\lambda(\hat{\mathbf d})
=\int_{A_\perp}L_{\lambda,source}\,dA_\perp,
\]

but the inverse is not possible in general. A signature-table provider is
therefore a valid high-fidelity provenance provider even though it has no
spatial capability.

For provider chaining, use a conservative neutral cross-section/flux handoff
rather than legacy zone types. Curved providers use the same consumer
capabilities and add provider-specific centerline/environment physics.
