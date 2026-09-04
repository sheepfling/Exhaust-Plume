from __future__ import annotations

from scripts.test_lanes import (
    TEST_LANE_SCHEMA,
    TEST_LANES,
    assert_lane_partition,
    lane_partition_report,
    pytest_command,
)


def test_test_lane_manifest_partitions_every_test_module_once() -> None:
    assert_lane_partition()

    report = lane_partition_report()

    assert report["schema"] == TEST_LANE_SCHEMA
    assert report["assigned_test_count"] == report["test_count"]
    assert report["empty_patterns"] == {}
    assert report["overlaps"] == {}
    assert report["unassigned"] == ()
####


def test_mission_planar_and_chem0_lanes_have_explicit_focused_commands() -> None:
    lane_ids = {lane.lane_id for lane in TEST_LANES}
    mission_command = pytest_command(("mission-time-v1",), python="python")
    planar_command = pytest_command(("planar-moc-primitives-v1",), python="python")
    chem0_command = pytest_command(("thermochemistry-chem0-v1",), python="python")

    assert "mission-time-v1" in lane_ids
    assert "planar-moc-primitives-v1" in lane_ids
    assert "thermochemistry-chem0-v1" in lane_ids
    assert mission_command[:4] == ("python", "-m", "pytest", "-q")
    assert mission_command[-1] == "tests/src/products/test_mission_timeline.py"
    assert "tests/src/models/moc/test_primitives.py" in planar_command
    assert chem0_command[-1] == "tests/src/models/gas/test_frozen_mixture.py"
####
