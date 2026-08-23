from __future__ import annotations

import json
from pathlib import Path


def test_phase_0_gate_report_is_machine_readable_and_scope_bounded() -> None:
  report_path = Path(__file__).resolve().parents[3] / "docs" / "phase0_gate_report.json"
  report = json.loads(report_path.read_text())
  assert report["status"] == "pass"
  assert report["branch"] == "feature/plume-interface-foundation"
  assert report["verification"]["pytest"]["status"] == "pass"
  assert report["verification"]["ruff"]["status"] == "pass"
  assert report["verification"]["pyright"]["errors"] == 0
  assert "CPU/GPU acceleration" in report["scope"]["excluded"]
  assert "spectroscopy and radiation" in report["scope"]["excluded"]
  assert "thermochemistry and finite-rate chemistry" in report["scope"]["excluded"]
####
