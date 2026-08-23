# M0 Architecture Review

Status: recorded for the provider-interface foundation branch on 2026-08-22.
This review freezes the handoff boundary; it does not implement a provider or
change legacy solver behavior.

## Accepted execution boundary

The accepted ADR set is `13_architecture_decision_records.md`, ADR-001 through
ADR-014. The machine-readable capability registry is
`docs/coding_agent_handoff/provider_architecture.yaml`, schema version `1.0`.
Every capability is currently major version `1`.

The boundary for the next interface packet is:

- A single provider/session/snapshot lifecycle serves both signature and
  spatial consumers.
- Consumers request semantic capabilities, not provider-specific zone or mesh
  types.
- Geometry is optional and may be `INTERNAL_ONLY`, `EXPOSED_APPROXIMATE`, or
  `EXPOSED_VALIDATED`.
- The plume-local frame is right-handed with origin at the nozzle/source
  reference and `+X` downstream. Directional products receive a finite unit
  `source_to_observer_direction_plume`.
- Intrinsic source signatures exclude range, atmosphere, optics, and detector
  response.
- SI units and radians are canonical for new interfaces. The current alpha
  solver’s degree-based fields remain a documented compatibility boundary.
- Invalid configuration is rejected; physical non-solutions and termination
  are structured results rather than silent nominal values.

## Decision closure for the opening wave

| Decision | Opening-wave disposition |
| --- | --- |
| ADR-010 / DEC-005: dependency policy | Use the handoff working default: NumPy/SciPy/Pydantic/PyYAML may be base dependencies; spectroscopy and chemistry remain optional. Dependency edits belong to their implementation packet. |
| ADR-011 / DEC-004: boundary/result representation | Use Pydantic at configuration/serialization boundaries and frozen dataclasses for computational states, with explicit adapters. |
| DEC-001: planar versus axisymmetric first cell | Planar MOC remains the opening physics default; no axisymmetric claim is permitted. |
| DEC-002: overexpanded scope | Keep applicability and source metadata explicit; do not introduce a universal pressure-ratio threshold. |
| DEC-003: Mach-disk classifier | Require local attached-shock feasibility before any separately sourced empirical criterion. |
| DEC-006–DEC-011 | Deferred to the phase gates named in the risk register; none blocks provider contracts or foundation contracts. |

## Gate result

The reviewed branch and source blobs match the handoff snapshot. The existing
ADRs, capability registry, API migration policy, and open-decision defaults do
not block M1/I0 or M2/FND-A. The legacy API remains unchanged at this point;
the next eligible implementation packet is M1/I0 provider contract foundation.
