# Phase 1 first-cell evidence report

Status: **partial evidence; release gate not passed**  
Source tranche: `b913938` (`feat: add fully expanded first-cell diagnostics`)  
Branch: `work/validation-and-completion`

This report records the first-cell correlation and resolution evidence added to
the isolated completion branch. It does not promote the compatibility-backed
straight solver, the open planar MOC lattice, or the recovered corpus into a
closed physical shock-cell or product-level validation claim.

## Scope and fidelity boundary

This tranche adds two independent diagnostics under
`src/exhaust_plume/models/shock_cells/`:

- `fully_expanded.py` constructs an isentropic equivalent state at
  (p_j=p_a), including the equivalent Mach number, area ratio, diameter, and
  state reconstruction.
- `correlations.py` evaluates the classical near-adapted circular-jet spacing
  relation and reports solver-versus-correlation error when a physical solver
  length is actually available.

The basic straight solver does not call either diagnostic automatically. The
diagnostics do not close the reflected MOC zone, add a Mach disk, infer a shock
train, or alter the visual, signature, optical, or focal-plane-array product
lanes.

## Governing equations and assumptions

For a calorically perfect gas, the equivalent fully expanded Mach number is

\[
M_j = \sqrt{\frac{2}{\gamma-1}
  \left[\left(\frac{p_0}{p_a}\right)^{(\gamma-1)/\gamma}-1\right]}.
\]

The area--Mach function is

\[
\mathcal A(M)=\frac{1}{M}
 \left[\frac{2}{\gamma+1}
  \left(1+\frac{\gamma-1}{2}M^2\right)\right]
 ^{(\gamma+1)/(2(\gamma-1))},
\]

with

\[
\frac{A_j}{A_e}=\frac{\mathcal A(M_j)}{\mathcal A(M_e)},
\qquad
D_j=D_e\sqrt{A_j/A_e}.
\]

The comparison spacing is

\[
L_{s,\mathrm{corr}}=1.306D_j\sqrt{M_j^2-1}.
\]

The relation is a comparison metric only. It is not imposed on the computed
geometry. The implementation assumes a uniform circular supersonic exit,
constant gamma, isentropic total-to-static reconstruction, and no total
pressure loss. A matched exit (`p_e/p_a` within the configured tolerance)
returns an explicit `no_first_cell_claim` result. A case whose equivalent
state is sonic or subsonic is reported outside the lane rather than coerced
through the supersonic exit-state contract.

## Local reference cases

The underexpanded reference used for the MOC diagnostic is:

| quantity | value |
| --- | ---: |
| (M_e) | 2.0 |
| (p_0) | 2,000,000 Pa |
| (T_0) | 900 K |
| (D_e) | 0.10 m |
| (p_a) | 101,325 Pa |
| (p_e/p_a) | 2.5226652 |
| (M_j) | 2.5929830 |
| (D_j) | 0.1305692 m |
| (L_{s,\mathrm{corr}}) | 0.4079595 m |

The MOC fan, reflected free-boundary march, and characteristic-zone assembly
all converge for this case at (N=4,8,16). The returned zone is still open
physically: its `shock_closure_status` is `not_assembled` and its
`physical_closure_status` is `open`.

The fan/reflected interface is not yet a shared physical grid. The fan stores
lip-ray centerline intersections while the reflected march solves averaged
compatibility geometry; the explicit interface check reports a maximum
coordinate residual of 0.1405629941 m for the canonical N=8 case. The cells
remain separate diagnostic meshes until a characteristic interface
construction reconciles those coordinates.

The boundary-side attached-shock candidate now records a downstream total
pressure of 1,849,892.35 Pa and a total-pressure ratio of 0.9249462 relative to
its local upstream state. This is a valid post-shock state diagnostic, not a
claim that the candidate has been continued through a closed characteristic
zone.

The mild overexpanded diagnostic case uses (M_e=3) and (p_e/p_a=0.9).
The existing basic solver returns one construction cell at its configured
boundary, but that result is not an attached-overexpanded MOC first-cell
closure. The MOC compression/shock candidate remains a separate, incomplete
lane. A matched (M_e=3), (p_e/p_a=1) case returns no first-cell
correlation claim.

## Open-lattice resolution study

These are metrics of the current reflected characteristic lattice, not
physical first-cell metrics. `open extent` is included only to expose the
geometric truncation and must not be renamed `first_cell_length`.

| fan count (N) | nodes | cells | coverage area (m²) | max radius (m) | open extent x (m) | max pressure residual | max tangent residual | max invariant residual |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 15 | 14 | 0.04008720815 | 0.1495180844 | 0.7443014497 | 1.44e-16 | 0 | 1.85e-12 |
| 8 | 45 | 44 | 0.04041915265 | 0.1492695783 | 0.7431488333 | 1.44e-16 | 0 | 1.85e-12 |
| 16 | 153 | 152 | 0.04050155232 | 0.1492075095 | 0.7428606519 | 1.44e-16 | 0 | 1.85e-12 |

The area, maximum-radius, and open-extent differences are monotone for these
three resolutions. Their estimated observed orders are approximately 2.01,
2.00, and 2.00 respectively. This is evidence for the numerical open-lattice
construction only; it is not a convergence acceptance for a physical first
cell because the shock endpoint, post-shock characteristic continuation, and
downstream continuation are absent. The physical first-cell length and solver-to-
correlation relative error are therefore recorded as **not available**.

## Correlation comparison

The equivalent-state diagnostic is available for both the underexpanded and
mild overexpanded local cases:

| case | (M_j) | (D_j) (m) | correlation spacing (m) | solver length | relative error |
| --- | ---: | ---: | ---: | --- | --- |
| underexpanded (p_e/p_a=1.1), (M_e=3), (D_e=2) m | 3.0637361 | 2.0616012 | 7.7971821 | not assembled | not available |
| mild overexpanded (p_e/p_a=0.9), (M_e=3), (D_e=2) m | 2.9299894 | 1.9344043 | 6.9576660 | not assembled | not available |
| canonical MOC case | 2.5929830 | 0.1305692 | 0.4079595 | open lattice only | not available |
| matched (p_e/p_a=1) | (M_e) | (D_e) | no claim | no claim | no claim |

No correlation mismatch is hidden by loosening a tolerance. A solver length is
not reported for the open MOC lattice because the shock closure required to
define it has not been assembled.

## Recovered validation corpus

The user-provided `plume_validation_data_v8.zip` has SHA-256
`79c2a34dd4c43bd976ceb8773fdccd78a2592d903bf03ca57c2aef82f882e9aa`. Its 138
members and 137 internal checksums were verified, and its bundled corpus test
set passed 57 tests. The archive contains the embedded product/alignment
overlay, but the separately named
`plume_mvp_validation_alignment_v1.zip` remains missing. The detailed intake
record is [corpus_intake_report_v1.json](corpus_intake_report_v1.json).

The recovered `CJ-UEJ-001` data are useful supporting cold-gas component
evidence, but they do not close this Phase 1 gate: the source lacks total
temperature, the adapter is near-sonic while the current exit contract is
supersonic, and the current solver does not resolve a physical shock train.
The existing component report therefore remains `claim_status: not_accepted`.
The provider-specific visual, signature, ray/optical, and FPA comparisons
also remain pending their measurement-space outputs and scenario/operator
bindings.

## Validity failures and open gates

- Strong or detached overexpanded cases are not forced through the mild
  attached topology.
- No nozzle separation model is claimed.
- The open reflected characteristic zone is not a closed shock cell.
- The fan lip-ray grid and reflected averaged-compatibility grid are not
  coincident; they must not be combined by coordinate snapping or an inferred
  shared edge.
- The post-shock candidate has no neighboring characteristic continuation.
- No finite downstream shock train or physical termination is inferred.
- No independent planar MOC reference family is bound to the current solver.
- No disjoint calibration/validation split is available for reduced-order
  shock-cell closure.
- The separate MVP alignment archive is still missing.

## Quality and performance evidence

After the current completion-branch updates, the repository suite reports
`422 passed, 18 warnings`.
Ruff and Pyright both pass. The full suite wall time was 12.90 s in the
isolated completion worktree. The focused MOC resolution sweep completed in
under 0.6 s including interpreter startup; solver-only timing and peak memory
were not instrumented and are intentionally not presented as benchmark
evidence.

The refinement table is guarded by
`tests/src/models/shock_cells/test_first_cell_convergence.py`. That test
checks the monotone diagnostic metrics and explicitly requires the physical
and shock closure statuses to remain open.

## Release decision

This report passes the local equation, contract, matched-flow, scaling, and
open-lattice diagnostic checks. It does **not** pass the Phase 1 release gate.
The next required tranche is an explicitly reconciled characteristic interface,
then a physically closed, independently referenced underexpanded first cell
plus a mild attached overexpanded case, followed by a provider-bound external
comparison. Until then, the basic visualization and signature products may use
their existing bounded lanes, while the planar MOC and higher-fidelity
shock-cell lane remain explicitly experimental and separate.
