# Coding-Agent Prompts and Phase-Gate Checklists

## 1. Purpose

This document indexes ready-to-paste prompts for each implementation phase and
provides the reviewer checklist that must be completed before advancing.

## 2. Prompt index

1. [`prompts/01_phase_0b_foundation_completion.md`](prompts/01_phase_0b_foundation_completion.md)
2. [`prompts/02_phase_1_validated_first_cell.md`](prompts/02_phase_1_validated_first_cell.md)
3. [`prompts/03_phase_2_finite_shock_train.md`](prompts/03_phase_2_finite_shock_train.md)
4. [`prompts/04_phase_3_integral_mixing.md`](prompts/04_phase_3_integral_mixing.md)
5. [`prompts/05_phase_4_gray_radiation.md`](prompts/05_phase_4_gray_radiation.md)
6. [`prompts/06_phase_5_spectral_radiation.md`](prompts/06_phase_5_spectral_radiation.md)
7. [`prompts/07_phase_6_thermochemistry.md`](prompts/07_phase_6_thermochemistry.md)

The existing [`11_coding_agent_kickoff_prompt.md`](11_coding_agent_kickoff_prompt.md)
starts the first Phase 0 issue group.

## 3. How to use a prompt

1. Start from the branch/commit that passed the previous phase gate.
2. Paste one phase prompt to the coding agent.
3. Require the agent to select only the first dependency-ready issue group.
4. Review the completion report and diff.
5. Run the gate independently.
6. Continue with the next issue group using the same prompt and updated context.
7. Begin the next phase only after every checklist item is evidenced.

A prompt grants no permission to skip tests or combine unrelated issues.

## 4. Universal reviewer checklist

- [ ] The change implements only the stated issue group.
- [ ] Governing equations, correlations, and closures are labeled correctly.
- [ ] New or changed functions are fully typed.
- [ ] New/materially changed scopes end with `####`.
- [ ] Existing TODOs are preserved or explicitly resolved.
- [ ] Failure returns structured status or typed exception.
- [ ] SI units and radians are used internally.
- [ ] Focused tests demonstrate the defect or contract.
- [ ] Full tests, Ruff, Pyright, and build pass.
- [ ] Installed-wheel behavior is checked when exports/dependencies change.
- [ ] Numerical evidence includes residuals and convergence, not only plots.
- [ ] Compatibility impact is documented.
- [ ] Remaining validity limits are explicit.

## 5. Phase 0 gate

- [ ] Choked mass-flow equation corrected.
- [ ] Gas molecular weight honored everywhere in generic paths.
- [ ] Energy and enthalpy names are physically correct.
- [ ] Weak/strong zero-turn limits pass.
- [ ] Maximum attached-turn gate passes.
- [ ] Matched flow returns zero cells.
- [ ] Forward-ray geometry rejects invalid intersections.
- [ ] Precursor geometry uses radians and `R/tan(beta)`.
- [ ] No public closed-zone `NaN` geometry remains.
- [ ] Legacy exports and wheel smoke pass.
- [ ] Python 3.12/type-checking target is truthful.

## 6. Phase 1 gate

- [ ] PM inverse is bounded and verified.
- [ ] Characteristic sign convention is documented and tested.
- [ ] Interior compatibility residuals pass.
- [ ] Centerline `theta=0` residual passes.
- [ ] Free-boundary `p=p_a` residual passes.
- [ ] Underexpanded first cell closes.
- [ ] Supported overexpanded first cell closes or rejects by validity policy.
- [ ] Detached/Mach-disk topology is explicit.
- [ ] Closed-zone topology validation passes.
- [ ] Three-level refinement study shows convergence.

## 7. Phase 2 gate

- [ ] Cell count is an output.
- [ ] Closure coefficients have calibration artifacts.
- [ ] Calibration/validation datasets are disjoint.
- [ ] Core diameter and pressure amplitude evolve consistently.
- [ ] Physical and safety termination are distinct.
- [ ] Applicability bounds are enforced.
- [ ] Sensitivity and identifiability are reported.
- [ ] Uncertainty reaches cell count and endpoint.

## 8. Phase 3 gate

- [ ] Mass balance passes.
- [ ] Momentum balance passes.
- [ ] Total-enthalpy balance passes.
- [ ] Frozen species/element balances pass.
- [ ] Primitive recovery preserves positivity.
- [ ] Physical events and domain truncation are distinct.
- [ ] Field reconstruction preserves integral fluxes.

## 9. Phase 4 gate

- [ ] Planck implementation and units pass.
- [ ] Homogeneous slab matches exact solution.
- [ ] Thin/thick limits pass.
- [ ] Layer ordering passes.
- [ ] Ray geometry matches analytic references.
- [ ] Image and angular integrals converge.
- [ ] Optically thin angle-invariance test passes.
- [ ] IR-domain endpoint is separate.

## 10. Phase 5 gate

- [ ] Spectroscopic tables are content-addressed.
- [ ] Reference cross sections pass.
- [ ] Interpolation error is bounded.
- [ ] Mixture number density and opacity pass.
- [ ] Spectral coordinate conversion passes.
- [ ] Atmosphere, range, and sensor stages are separable.
- [ ] Heated-plume validation and uncertainty are documented.
- [ ] Optional dependencies do not break base import.

## 11. Phase 6 gate

- [ ] Species and elemental balances pass.
- [ ] CEA adapter is reproducible and offline-testable.
- [ ] Thermally perfect property inversion passes.
- [ ] Frozen variable-property waves conserve the right quantities.
- [ ] Equilibrium reference states pass.
- [ ] Finite-rate chemistry is energy consistent.
- [ ] Particle zero limit recovers molecular result.
- [ ] Particle optical data have provenance and applicability.

## 12. Escalation

Use the risk register and create a new ADR proposal when an implementation
choice changes public schema, base dependencies, scientific topology, or a phase
gate. The coding agent must not bury such decisions in a completion report.
