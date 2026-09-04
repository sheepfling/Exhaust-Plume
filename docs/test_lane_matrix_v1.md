# Focused test-lane matrix v1

Status: active development-routing policy.

The full test suite remains the integration gate. Focused lanes make local
work faster and keep evidence segregated: a passing lane validates only the
model or product named by that lane. It cannot promote a different fidelity,
radiation, transport, detector, or validation claim.

The executable manifest is [`scripts/test_lanes.py`](../scripts/test_lanes.py).
It partitions every test module exactly once, rejects empty selections and
overlaps, and is checked by CI.

## Use

```bash
python3 -m scripts.test_lanes --list
python3 -m scripts.test_lanes --lane mission-time-v1
python3 -m scripts.test_lanes --lane thermochemistry-chem0-v1
python3 -m scripts.test_lanes --lane visual-product-v1 --lane signature-product-v1
python3 -m scripts.test_lanes --lane planar-moc-primitives-v1 -- -x
python3 -m scripts.test_lanes --check
```

Use the full suite before handoff or release work:

```bash
python3 -m pytest -q
```

## Lane boundaries

| Lane | Focus | Must not be interpreted as |
| --- | --- | --- |
| `shared-contracts-v1` | API, contract, geometry, utility, and lifecycle invariants | Validation of a particular flow, radiation, or detector lane |
| `thermochemistry-chem0-v1` | CHEM-0 frozen-mixture properties, composition conversion, and state provenance | Reaction closure, molecular-population inference, validated radiation, or production thermochemistry |
| `shock-cell-basic-v1` | Fast steady shock-cell and straight visual behavior | Signature, ray-transfer, detector, or high-fidelity promotion |
| `shock-cell-reduced-order-v1` | Resolved-first-cell plus reduced-order shock-train continuation | Downstream resolved-MOC evidence |
| `straight-integral-v1` | Straight integral conservation and domain behavior | Radiation or detector evidence |
| `washed-integral-v1` | Curved/wash/entrainment integral behavior | Automatic ray-transfer or signature evidence |
| `planar-moc-primitives-v1` | Planar MOC primitives, closure, chain, and refinement work | Axisymmetric visual-provider or signature-provider validation |
| `visual-product-v1` | Canonical visual products, standardization, and galleries | A physics upgrade beyond the source lane’s declared ceiling |
| `signature-product-v1` | Lookup, gray transport, far-field, and guarded bridge behavior | Inferred chemistry, unimplemented curved transport, or detector validation |
| `mission-time-v1` | Time stepping, snapshot lineage, and temporal product composition | Solver-owned propulsion, atmosphere, or chemistry closure validation |
| `focal-plane-array-v1` | Downstream detector and focal-plane integration | Promotion of its upstream plume/ray input |
| `governance-and-validation-v1` | Release boundaries, corpus handling, lane guards, and comparisons | Replacement for lane-local physical evidence |

The visual and signature product lanes intentionally include cross-lane
adapters. Their tests assert the adapter’s declared readiness and claim
ceiling; they do not merge the underlying model lanes. In particular, the
curved-integral and planar-MOC paths must report a typed signature block until
their own transport providers exist.
