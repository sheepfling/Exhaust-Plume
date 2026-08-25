from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
  required = (
      'START_HERE.md',
      'README.md',
      'planning/work_plan.yaml',
      'planning/execution_graph.yaml',
      'planning/github_issues.csv',
      'planning/acceptance_gates.yaml',
      'planning/release_gates.yaml',
  )
  for rel in required:
    assert (ROOT / rel).is_file(), rel
  ####

  work = yaml.safe_load((ROOT / 'planning/work_plan.yaml').read_text(encoding='utf-8'))
  graph = yaml.safe_load((ROOT / 'planning/execution_graph.yaml').read_text(encoding='utf-8'))
  packet_ids = [item['id'] for item in work['packets']]
  assert len(packet_ids) == len(set(packet_ids))
  assert set(graph['nodes']) == set(packet_ids)
  for edge in graph['edges']:
    assert edge['from'] in packet_ids
    assert edge['to'] in packet_ids
  ####

  with (ROOT / 'planning/github_issues.csv').open(encoding='utf-8', newline='') as handle:
    rows = list(csv.DictReader(handle))
  assert {row['id'] for row in rows} == set(packet_ids)
  for row in rows:
    assert (ROOT / row['packet_file']).is_file()
  ####

  manifest = json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf-8'))
  for item in manifest['files']:
    path = ROOT / item['path']
    assert path.is_file(), item['path']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == item['sha256'], item['path']
  ####

  print(f"validated {len(packet_ids)} packets and {len(manifest['files'])} files")
####


if __name__ == '__main__':
  main()
####
