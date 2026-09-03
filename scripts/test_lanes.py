"""Run the repository's focused, fidelity-scoped test lanes.

The normal full suite remains the integration gate.  This manifest is the
faster development routing layer: every test module belongs to exactly one
lane, so a focused pass cannot silently borrow coverage or a validation claim
from a different model/product lane.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_LANE_SCHEMA = "plume.test-lanes@1"


@dataclass(frozen=True, slots=True)
class TestLane:
    """One non-overlapping focused test selection and its claim boundary."""

    lane_id: str
    purpose: str
    claim_boundary: str
    patterns: tuple[str, ...]


TEST_LANES = (
    TestLane(
        lane_id="shared-contracts-v1",
        purpose="Shared API, contract, geometry, utility, and provider-lifecycle invariants.",
        claim_boundary="Contract correctness only; it does not validate any individual flow or signature lane.",
        patterns=(
            "tests/conformance/test_*.py",
            "tests/installed_smoke.py",
            "tests/src/api/test_*.py",
            "tests/src/compat/test_*.py",
            "tests/src/contracts/test_*.py",
            "tests/src/geometry/test_*.py",
            "tests/src/log/test_*.py",
            "tests/src/util/**/test_*.py",
            "tests/src/models/gas/test_*.py",
            "tests/src/models/nozzle/test_*.py",
            "tests/src/products/test_cli_mvp.py",
            "tests/src/products/test_product_contracts.py",
            "tests/src/products/test_products.py",
            "tests/src/providers/test_existing_model_adapters.py",
            "tests/src/providers/test_product_fixtures.py",
            "tests/src/providers/test_provider_alignment.py",
            "tests/src/providers/test_provider_lifecycle.py",
        ),
    ),
    TestLane(
        lane_id="shock-cell-basic-v1",
        purpose="Fast, steady analytical shock-cell and straight visual behavior.",
        claim_boundary="Engineering geometry/flow checks only; no signature, ray-transfer, detector, or high-fidelity promotion.",
        patterns=(
            "tests/src/models/shock_cells/test_*.py",
            "tests/src/models/plume/test_motor_parameters.py",
            "tests/src/models/plume/test_overexpanded_precursor.py",
            "tests/src/models/plume/test_plot_projected_areas.py",
            "tests/src/models/plume/test_plume_solver.py",
            "tests/src/models/plume/test_run_plume_solve.py",
            "tests/src/providers/test_shock_cell_visual.py",
            "tests/src/providers/test_shock_diamond.py",
            "tests/src/providers/test_straight_analytical.py",
            "tests/src/providers/test_straight_visual.py",
            "tests/src/validation/test_phase_0_gate.py",
            "tests/src/validation/test_validity_matrix.py",
        ),
    ),
    TestLane(
        lane_id="shock-cell-reduced-order-v1",
        purpose="Resolved-first-cell plus reduced-order shock-train continuation.",
        claim_boundary="Calibrated reduced-order continuation only; it is not downstream resolved-MOC evidence.",
        patterns=(
            "tests/src/models/shock_train/test_*.py",
            "tests/src/providers/test_shock_train_visual.py",
            "tests/src/validation/test_shock_train_comparisons.py",
        ),
    ),
    TestLane(
        lane_id="straight-integral-v1",
        purpose="Straight integral plume conservation and bounded-domain behavior.",
        claim_boundary="Integral/reference flow evidence only; it does not create a radiation or detector claim.",
        patterns=("tests/src/models/integral/test_*.py",),
    ),
    TestLane(
        lane_id="washed-integral-v1",
        purpose="Curved, washed, entraining integral plume behavior.",
        claim_boundary="Curved visual/engineering flow evidence only; no automatic ray-transfer or signature promotion.",
        patterns=("tests/src/models/plume/test_curved_*.py",),
    ),
    TestLane(
        lane_id="planar-moc-primitives-v1",
        purpose="Planar MOC primitives, coupled closure, chains, and refinement evidence.",
        claim_boundary="Planar research/foundation evidence only; it is not an axisymmetric visual or signature provider claim.",
        patterns=(
            "tests/src/models/moc/test_*.py",
            "tests/src/validation/test_cj_uej_component_validation.py",
            "tests/src/validation/test_moc_*.py",
        ),
    ),
    TestLane(
        lane_id="visual-product-v1",
        purpose="Renderer-neutral visual products, standardization, and galleries.",
        claim_boundary="Visualization integrity only; tests retain source-lane claim ceilings.",
        patterns=(
            "tests/src/products/test_model_visualization.py",
            "tests/src/products/test_visual_mvp.py",
            "tests/src/products/test_visualization_gallery.py",
            "tests/src/providers/test_prescribed_visual.py",
            "tests/src/providers/test_curved_visual.py",
            "tests/src/providers/test_moc_visual.py",
            "tests/src/validation/test_visual_comparisons.py",
        ),
    ),
    TestLane(
        lane_id="signature-product-v1",
        purpose="Spectral lookup, gray ray transfer, far-field integration, and guarded model bridges.",
        claim_boundary="Signature/ray contract evidence only; optical profile and transport readiness remain explicit.",
        patterns=(
            "tests/src/products/test_model_signature.py",
            "tests/src/products/test_signature_mvp.py",
            "tests/src/products/test_signature_timeline.py",
            "tests/src/providers/test_gray_ray_transfer.py",
            "tests/src/providers/test_curved_gray_ray_transfer.py",
            "tests/src/providers/test_signature_table.py",
            "tests/src/radiation/test_*.py",
            "tests/src/validation/test_measurement_operators.py",
            "tests/src/validation/test_sensor_operators.py",
            "tests/src/validation/test_spectral_comparisons.py",
        ),
    ),
    TestLane(
        lane_id="mission-time-v1",
        purpose="Prescribed trajectory/state advancement plus visual/signature snapshot lineage.",
        claim_boundary="Scheduling and reproducibility only; physical engine, atmosphere, and chemistry closures remain resolver-owned.",
        patterns=("tests/src/products/test_mission_timeline.py",),
    ),
    TestLane(
        lane_id="focal-plane-array-v1",
        purpose="Downstream camera, detector, and focal-plane integration behavior.",
        claim_boundary="Detector-adapter evidence only; it never upgrades an upstream plume or ray-transfer claim.",
        patterns=(
            "tests/src/products/test_fpa_gallery.py",
            "tests/src/validation/test_fpa_*.py",
        ),
    ),
    TestLane(
        lane_id="governance-and-validation-v1",
        purpose="Lane boundaries, release evidence, validation corpus, and cross-product governance.",
        claim_boundary="Governance and acceptance logic only; it does not replace lane-local physics validation.",
        patterns=(
            "tests/src/providers/test_solver_fidelity_boundaries.py",
            "tests/src/validation/test_api_freeze.py",
            "tests/src/validation/test_external_corpus_alignment.py",
            "tests/src/validation/test_interface_v1_gate.py",
            "tests/src/validation/test_lane_*.py",
            "tests/src/validation/test_product_lane_validation.py",
            "tests/src/validation/test_provider_comparisons.py",
            "tests/src/validation/test_validation_claims.py",
            "tests/src/validation/test_validation_corpus_intake.py",
            "tests/src/validation/test_test_lanes.py",
        ),
    ),
)


def lane_by_id(lane_id: str) -> TestLane:
    """Return one declared lane or fail with the available lane IDs."""

    for lane in TEST_LANES:
        if lane.lane_id == lane_id:
            return lane
    available = ", ".join(lane.lane_id for lane in TEST_LANES)
    raise ValueError(f"unknown test lane {lane_id!r}; expected one of: {available}")


def lane_test_paths(lane: TestLane, *, root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Expand a lane's declared test patterns deterministically."""

    paths = {path for pattern in lane.patterns for path in root.glob(pattern) if path.is_file()}
    return tuple(sorted(paths))


def all_test_paths(*, root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Return all repository test modules that must have one focus lane."""

    paths = set((root / "tests").rglob("test_*.py"))
    installed_smoke = root / "tests" / "installed_smoke.py"
    if installed_smoke.is_file():
        paths.add(installed_smoke)
    return tuple(sorted(path for path in paths if path.is_file()))


def lane_partition_report(*, root: Path = REPO_ROOT) -> dict[str, object]:
    """Report empty patterns, overlaps, and unassigned test modules."""

    assignments: dict[Path, list[str]] = {}
    empty_patterns: dict[str, list[str]] = {}
    for lane in TEST_LANES:
        lane_paths = lane_test_paths(lane, root=root)
        for path in lane_paths:
            assignments.setdefault(path, []).append(lane.lane_id)
        unmatched = [pattern for pattern in lane.patterns if not tuple(root.glob(pattern))]
        if unmatched:
            empty_patterns[lane.lane_id] = unmatched
    expected = set(all_test_paths(root=root))
    assigned = set(assignments)
    return {
        "schema": TEST_LANE_SCHEMA,
        "lane_ids": tuple(lane.lane_id for lane in TEST_LANES),
        "test_count": len(expected),
        "assigned_test_count": len(assigned),
        "empty_patterns": empty_patterns,
        "overlaps": {str(path.relative_to(root)): tuple(lane_ids) for path, lane_ids in assignments.items() if len(lane_ids) != 1},
        "unassigned": tuple(str(path.relative_to(root)) for path in sorted(expected - assigned)),
    }


def assert_lane_partition(*, root: Path = REPO_ROOT) -> None:
    """Raise when the focused test-lane manifest no longer partitions tests."""

    report = lane_partition_report(root=root)
    problems: list[str] = []
    empty_patterns = report["empty_patterns"]
    overlaps = report["overlaps"]
    unassigned = report["unassigned"]
    if empty_patterns:
        problems.append(f"empty patterns: {empty_patterns}")
    if overlaps:
        problems.append(f"overlapping test assignments: {overlaps}")
    if unassigned:
        problems.append(f"unassigned tests: {unassigned}")
    if problems:
        raise ValueError("test-lane manifest is invalid: " + "; ".join(problems))


def pytest_command(
    lane_ids: Iterable[str],
    *,
    python: str = sys.executable,
    extra_pytest_args: Sequence[str] = (),
) -> tuple[str, ...]:
    """Build a deterministic focused pytest command for one or more lanes."""

    selected = tuple(lane_by_id(lane_id) for lane_id in lane_ids)
    if not selected:
        raise ValueError("at least one test lane is required")
    targets = tuple(str(path.relative_to(REPO_ROOT)) for lane in selected for path in lane_test_paths(lane))
    return (python, "-m", "pytest", "-q", *extra_pytest_args, *targets)


def _print_lanes() -> None:
    for lane in TEST_LANES:
        print(f"{lane.lane_id}: {lane.purpose}")
        print(f"  boundary: {lane.claim_boundary}")
        print(f"  tests: {len(lane_test_paths(lane))}")


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--lane", action="append", choices=tuple(lane.lane_id for lane in TEST_LANES))
    selection.add_argument("--all", action="store_true", help="run every focused lane in manifest order")
    parser.add_argument("--list", action="store_true", help="list lanes, boundaries, and test counts")
    parser.add_argument("--check", action="store_true", help="verify exact test-module partitioning without running pytest")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="extra pytest arguments after --")
    args = parser.parse_args(argv)
    try:
        assert_lane_partition()
    except ValueError as error:
        parser.error(str(error))
    if args.list:
        _print_lanes()
        return 0
    if args.check:
        print(f"{TEST_LANE_SCHEMA}: {len(TEST_LANES)} lanes partition {len(all_test_paths())} test modules")
        return 0
    lane_ids = tuple(lane.lane_id for lane in TEST_LANES) if args.all else tuple(args.lane or ())
    if not lane_ids:
        parser.error("choose --lane, --all, --list, or --check")
    command = pytest_command(lane_ids, extra_pytest_args=tuple(args.pytest_args))
    print("$ " + " ".join(command))
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
