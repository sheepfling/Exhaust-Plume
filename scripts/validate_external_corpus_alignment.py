"""Preflight the recovered Version 8 corpus against Exhaust-Plume contracts."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from zipfile import ZipFile

try:
  from scripts.verify_validation_corpus import load_manifest, verify_archive
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from verify_validation_corpus import load_manifest, verify_archive


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED_OPERATOR_REGISTRY = (
  REPO_ROOT
  / 'docs'
  / 'coding_agent_handoff'
  / 'resync_v0.1.0a1'
  / 'alignment'
  / 'measurement_operator_registry.csv'
)
SEMANTIC_CROSSWALK = REPO_ROOT / 'docs' / 'validation' / 'operator_semantic_crosswalk_v1.json'
PRIMARY_PRODUCTS = {
  'plume.visual.sectioned-tube@1',
  'plume.signature.spectral-radiant-intensity@1',
  'plume.optical.spectral-ray-transfer@1',
}
VISUAL_PRODUCT = 'plume.visual.sectioned-tube@1'
SIGNATURE_PRODUCT = 'plume.signature.spectral-radiant-intensity@1'
RAY_PRODUCT = 'plume.optical.spectral-ray-transfer@1'


def _load_semantic_crosswalk() -> tuple[dict[str, Any], ...]:
  payload = json.loads(SEMANTIC_CROSSWALK.read_text(encoding='utf-8'))
  entries = payload.get('entries')
  if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
    raise ValueError('operator semantic crosswalk must contain an entries list of objects')
  return tuple(dict(entry) for entry in entries)


REVIEWED_SEMANTIC_CROSSWALKS = _load_semantic_crosswalk()


def _validate_semantic_crosswalk(committed_operator_ids: Iterable[str]) -> dict[str, Any]:
  committed_set = set(committed_operator_ids)
  errors: list[str] = []
  external_ids: list[str] = []
  referenced_internal_ids: set[str] = set()
  for index, entry in enumerate(REVIEWED_SEMANTIC_CROSSWALKS):
    external_id = entry.get('external_operator_id')
    if not isinstance(external_id, str) or not external_id:
      errors.append(f'crosswalk entry {index} has no external operator ID')
      continue
    external_ids.append(external_id)
    internal_ids = entry.get('internal_operator_ids')
    if not isinstance(internal_ids, list) or not all(isinstance(item, str) for item in internal_ids):
      errors.append(f'crosswalk entry {external_id} has invalid internal_operator_ids')
      internal_ids = []
    referenced_internal_ids.update(internal_ids)
    candidates = entry.get('candidate_internal_operator_ids', [])
    if not isinstance(candidates, list) or not all(isinstance(item, str) for item in candidates):
      errors.append(f'crosswalk entry {external_id} has invalid candidate_internal_operator_ids')
      candidates = []
    referenced_internal_ids.update(candidates)
    if entry.get('mapping_kind') == 'no-safe-equivalent' and internal_ids:
      errors.append(f'no-safe-equivalent entry {external_id} has executable internal IDs')
    if entry.get('claim_status') != 'not_accepted':
      errors.append(f'crosswalk entry {external_id} does not retain not_accepted claim status')
    for field in ('mapping_kind', 'review_status', 'scope', 'unresolved_differences'):
      if field not in entry:
        errors.append(f'crosswalk entry {external_id} is missing {field}')
  duplicates = sorted({external_id for external_id in external_ids if external_ids.count(external_id) > 1})
  errors.extend(f'duplicate crosswalk external operator ID: {external_id}' for external_id in duplicates)
  unknown_internal_ids = sorted(referenced_internal_ids - committed_set)
  if unknown_internal_ids:
    errors.append(f'crosswalk references unknown internal operator IDs: {unknown_internal_ids!r}')
  return {
    'entry_count': len(REVIEWED_SEMANTIC_CROSSWALKS),
    'external_operator_ids': sorted(set(external_ids)),
    'referenced_internal_operator_ids': sorted(referenced_internal_ids),
    'unknown_internal_operator_ids': unknown_internal_ids,
    'errors': errors,
    'status': 'valid' if not errors else 'invalid',
  }


def _resolve_member(archive: ZipFile, relative_path: str) -> str:
  candidates = tuple(
    name for name in archive.namelist()
    if name == relative_path or name.endswith(f'/{relative_path}')
  )
  if len(candidates) != 1:
    raise ValueError(f'expected one archive member ending in {relative_path!r}, found {candidates!r}')
  return candidates[0]


def _read_json(archive: ZipFile, relative_path: str) -> Any:
  return json.loads(archive.read(_resolve_member(archive, relative_path)).decode('utf-8'))


def _read_csv(archive: ZipFile, relative_path: str) -> list[dict[str, str]]:
  content = archive.read(_resolve_member(archive, relative_path)).decode('utf-8')
  return list(csv.DictReader(io.StringIO(content)))


def _records(value: Any, *, name: str) -> list[Mapping[str, Any]]:
  if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
    raise ValueError(f'{name} must be a list of objects')
  return value


def reconcile_operator_ids(
    external_alignment: Iterable[Mapping[str, Any]],
    committed_operator_ids: Iterable[str],
) -> dict[str, Any]:
  """Report namespace differences without guessing semantic aliases."""

  external_ids = sorted({
    str(record['measurement_operator_id'])
    for record in external_alignment
    if record.get('measurement_operator_id')
  })
  committed_ids = sorted(set(committed_operator_ids))
  external_set = set(external_ids)
  committed_set = set(committed_ids)
  semantic_crosswalk = _validate_semantic_crosswalk(committed_set)
  reviewed_external_ids = {
    str(item['external_operator_id'])
    for item in REVIEWED_SEMANTIC_CROSSWALKS
    if item.get('external_operator_id')
  }
  semantic_crosswalk_status = (
    'complete-scoped'
    if semantic_crosswalk['status'] == 'valid' and external_set <= reviewed_external_ids
    else 'pending'
  )
  return {
    'external_count': len(external_ids),
    'committed_count': len(committed_ids),
    'external_only': sorted(external_set - committed_set),
    'committed_only': sorted(committed_set - external_set),
    'exact_namespace_match': external_set == committed_set,
    'crosswalk_status': 'reconciled' if external_set == committed_set else 'pending',
    'semantic_crosswalk_status': semantic_crosswalk_status,
    'reviewed_semantic_crosswalks': [dict(item) for item in REVIEWED_SEMANTIC_CROSSWALKS],
    'semantic_crosswalk': semantic_crosswalk,
    'scoped_reviewed_external_only': sorted(external_set & reviewed_external_ids),
    'unreviewed_external_only': sorted(external_set - reviewed_external_ids),
  }


def _cross_product_rule_key(record: Mapping[str, Any]) -> tuple[tuple[str, ...], str, str]:
  source_ids = tuple(sorted(str(item) for item in record.get('source_product_ids', ())))
  return source_ids, str(record.get('target_product_id')), str(record.get('disposition'))


def _validate_alignment_records(
    product_definitions: list[Mapping[str, Any]],
    alignment_records: list[Mapping[str, Any]],
    cross_product_rules: list[Mapping[str, Any]],
    validation_gates: list[Mapping[str, Any]],
) -> dict[str, Any]:
  errors: list[str] = []
  product_ids = {str(record.get('product_id')) for record in product_definitions}
  if product_ids != PRIMARY_PRODUCTS:
    errors.append(f'primary product IDs differ: {sorted(product_ids)!r}')
  if len(alignment_records) != 78:
    errors.append(f'expected 78 alignment records, found {len(alignment_records)}')
  if len(cross_product_rules) != 7:
    errors.append(f'expected 7 cross-product rules, found {len(cross_product_rules)}')
  if len(validation_gates) != 11:
    errors.append(f'expected 11 validation gates, found {len(validation_gates)}')

  gate_eligible = [record for record in alignment_records if record.get('direct_product_gate_eligible')]
  for record in gate_eligible:
    if record.get('target_kind') != 'primary_product':
      errors.append(f"gate-eligible record {record.get('alignment_id')} does not target a primary product")
    if not record.get('measurement_operator_id'):
      errors.append(f"gate-eligible record {record.get('alignment_id')} has no measurement operator")
    if record.get('relationship') not in {
        'direct_product_observation',
        'measurement_space_product_observation',
    }:
      errors.append(f"gate-eligible record {record.get('alignment_id')} has an invalid relationship")

  rule_keys = {_cross_product_rule_key(record) for record in cross_product_rules}
  required_rules = {
    ((RAY_PRODUCT,), SIGNATURE_PRODUCT, 'allowed'),
    ((SIGNATURE_PRODUCT,), RAY_PRODUCT, 'prohibited'),
    ((VISUAL_PRODUCT,), SIGNATURE_PRODUCT, 'prohibited'),
    ((VISUAL_PRODUCT,), RAY_PRODUCT, 'prohibited'),
    ((SIGNATURE_PRODUCT,), VISUAL_PRODUCT, 'prohibited'),
  }
  missing_rules = sorted(required_rules - rule_keys)
  if missing_rules:
    errors.append(f'missing required cross-product rules: {missing_rules!r}')

  gate_statuses: dict[str, int] = {}
  for gate in validation_gates:
    status = str(gate.get('status'))
    gate_statuses[status] = gate_statuses.get(status, 0) + 1

  return {
    'product_ids': sorted(product_ids),
    'alignment_record_count': len(alignment_records),
    'gate_eligible_record_count': len(gate_eligible),
    'cross_product_rule_count': len(cross_product_rules),
    'validation_gate_count': len(validation_gates),
    'validation_gate_statuses': gate_statuses,
    'errors': errors,
    'structure_status': 'valid' if not errors else 'invalid',
  }


def _verify_internal_checksums(archive: ZipFile) -> dict[str, Any]:
  checksum_member = _resolve_member(archive, 'CHECKSUMS.sha256')
  lines = [
    line.strip() for line in archive.read(checksum_member).decode('utf-8').splitlines()
    if line.strip()
  ]
  mismatches: list[str] = []
  checked = 0
  names = set(archive.namelist())
  for line in lines:
    expected, relative = line.split(maxsplit=1)
    relative = relative.removeprefix('./')
    member = _resolve_member(archive, relative)
    actual = sha256(archive.read(member)).hexdigest()
    checked += 1
    if actual != expected:
      mismatches.append(relative)
  return {
    'checksum_entry_count': len(lines),
    'checked_file_count': checked,
    'mismatches': mismatches,
    'status': 'verified' if not mismatches and len(names) == len(lines) + 1 else 'invalid',
  }


def preflight_corpus(path: Path) -> dict[str, Any]:
  """Validate corpus structure and report release blockers explicitly."""

  manifest = load_manifest()
  spec = next(spec for spec in manifest['archives'] if spec['archive_id'] == 'validation-corpus-v8')
  archive_check = verify_archive(spec, path)
  report: dict[str, Any] = {
    'report_id': 'exhaust-plume-external-corpus-alignment-preflight-v1',
    'archive': {
      'path': str(path),
      'expected_sha256': spec['sha256'],
      'actual_sha256': archive_check.actual_sha256,
      'status': archive_check.status,
      'member_count': archive_check.member_count,
    },
  }
  if archive_check.status != 'verified':
    report.update({
      'status': 'invalid-archive',
      'release_ready': False,
      'errors': list(archive_check.errors),
    })
    return report

  with ZipFile(path) as archive:
    benchmark_definitions = _records(_read_json(archive, 'data/benchmark_definitions.json'), name='benchmark_definitions')
    product_definitions = _records(_read_json(archive, 'data/mvp_product_definitions.json'), name='mvp_product_definitions')
    alignment_records = _records(_read_json(archive, 'data/mvp_data_product_alignment.json'), name='mvp_data_product_alignment')
    cross_product_rules = _records(_read_json(archive, 'data/mvp_cross_product_rules.json'), name='mvp_cross_product_rules')
    validation_gates = _records(_read_json(archive, 'data/mvp_validation_gates.json'), name='mvp_validation_gates')
    source_manifest = _read_csv(archive, 'data/source_manifest.csv')
    corpus_inventory = _read_csv(archive, 'data/corpus_inventory.csv')
    alignment_summary = _read_csv(archive, 'data/mvp_alignment_summary.csv')
    committed_operator_ids = (
      row['operator_id']
      for row in csv.DictReader(COMMITTED_OPERATOR_REGISTRY.open(newline='', encoding='utf-8'))
    )
    structure = _validate_alignment_records(
      product_definitions,
      alignment_records,
      cross_product_rules,
      validation_gates,
    )
    count_errors = []
    for name, actual, expected in (
        ('benchmark_definitions', len(benchmark_definitions), 17),
        ('source_records', len(source_manifest), 19),
        ('indexed_products', len(corpus_inventory), 60),
        ('alignment_summary_rows', len(alignment_summary), 20),
    ):
      if actual != expected:
        count_errors.append(f'expected {expected} {name}, found {actual}')
    structure['errors'].extend(count_errors)
    report.update({
      'content_counts': {
        'benchmark_definitions': len(benchmark_definitions),
        'source_records': len(source_manifest),
        'indexed_products': len(corpus_inventory),
        'alignment_mappings': len(alignment_records),
        'alignment_summary_rows': len(alignment_summary),
      },
      'internal_checksums': _verify_internal_checksums(archive),
      'alignment': structure,
      'operator_reconciliation': reconcile_operator_ids(
        alignment_records,
        committed_operator_ids,
      ),
    })

  errors = list(structure['errors'])
  checksum_status = report['internal_checksums']['status']
  if checksum_status != 'verified':
    errors.append('internal corpus checksums did not verify')
  if report['operator_reconciliation']['semantic_crosswalk']['status'] != 'valid':
    errors.append('committed semantic operator crosswalk is invalid')
  operator_status = report['operator_reconciliation']['semantic_crosswalk_status']
  report.update({
    'status': 'preflight-valid-pending-release-gates' if not errors else 'invalid-content',
    'release_ready': False,
    'release_blockers': [
      'external operator semantic crosswalk is incomplete' if operator_status != 'complete-scoped' else None,
      'provider-specific VIS/SIG/RAY comparisons are recorded but not accepted',
      'separately named MVP alignment archive is not yet verified',
    ],
    'errors': errors,
  })
  report['release_blockers'] = [item for item in report['release_blockers'] if item is not None]
  return report


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = preflight_corpus(args.corpus)
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  print(serialized, end='')
  return 0 if report['status'] == 'preflight-valid-pending-release-gates' else 1


if __name__ == '__main__':
  raise SystemExit(main())
