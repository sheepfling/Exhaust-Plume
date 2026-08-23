from __future__ import annotations

import json
from pathlib import Path


def test_interface_v1_gate_report_is_generic_and_scope_bounded() -> None:
  report_path = Path(__file__).resolve().parents[3] / 'docs' / 'interface_v1_gate_report.json'
  report = json.loads(report_path.read_text(encoding='utf-8'))
  assert report['status'] == 'pass'
  assert report['branch'] == 'feature/plume-interface-foundation'
  assert report['verification']['schemas_and_fixtures']['status'] == 'pass'
  assert 'physical spectral/radiation provider' in report['scope']['excluded']
  assert 'CPU/GPU acceleration' in report['scope']['excluded']
####
