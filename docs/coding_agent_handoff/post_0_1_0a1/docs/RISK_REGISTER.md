# Risk register

| ID | Risk | Consequence | Mitigation | Gate |
|---|---|---|---|---|
| R-01 | Two public API systems continue to evolve | Permanent migration and schema divergence | Complete API-008A/B/C before new public providers | API-010 |
| R-02 | Pre-merge branch evidence is mistaken for release evidence | Unreproducible alpha | Commit-specific release report and artifact hashes | RLS-001 |
| R-03 | Low-order first-cell boundary is treated as validated MOC | False confidence in geometry | Keep explicit legacy/low-order fidelity until MOC-006 | MOC-007 |
| R-04 | A single zone is used as a control-surface handoff | Flux non-closure | Integrate all intersected regions and report residuals | HND-003 |
| R-05 | Curved coefficients are presented as helicopter-validated | Misleading trajectories | Preserve coefficient provenance and calibrate in ordered stages | WASH-005/MIX-002 |
| R-06 | Domain end is called physical plume end | Incorrect downstream products | Typed termination reasons and passive handoff | TERM-001 |
| R-07 | Visual envelope becomes an optical medium | Incorrect radiance | Separate geometry, field, and transfer capabilities | RAD-003 |
| R-08 | API consolidation breaks shipped fixtures | Consumer breakage | Freeze shipped wire shapes, compatibility adapters, schema diff | API-008C |
| R-09 | Curved swept tube folds or self-intersects | Invalid rendering/rays | Curvature/slenderness diagnostics and geometry quality checks | WASH-003/RAY-001 |
| R-10 | Calibration and validation reuse the same data | Optimistic error claims | Dataset registry and disjoint holdouts | MOC-006/MIX-002 |
| R-11 | Ambient momentum treatment is inconsistent | Conservation error in moving ambient | Re-derive straight integral equations and exact tests | MIX-001 |
| R-12 | Gray optical MVP is mistaken for molecular truth | Misuse of signatures | Explicit radiation claim and applicability labels | OPT-VAL-001 |
