# Exhaust-Plume Post-A1 Plan and Implementation Packet

This directory converts the `v0.1.0a1` repository resync into a bounded execution program for the coding agent. It preserves the agreed architecture and implementation decisions while removing work that is already complete in the release.

## Contents

- Release-accurate baseline and gap analysis.
- Canonical architecture and compatibility migration.
- Release targets for `0.1.0a2`, `0.1.0a3`, and later fidelity work.
- Fourteen one-PR implementation packets with file-level targets and acceptance gates.
- Machine-readable work plan, dependency graph, issue catalog, ownership map, and release gates.
- Reference-only Python skeletons for provider and conformance patterns.
- Reproducible packet validator, manifest, and checksums.

## Authority

`planning/work_plan.yaml` is authoritative for dependency ordering. Work-packet Markdown contains the human-readable implementation detail.

## Public-repository note

The original source transcripts/conversation exports used to derive this packet are intentionally not copied into this public repository. Their actionable architecture, defaults, constraints, and acceptance decisions are incorporated into the documents and machine-readable plans in this directory.
