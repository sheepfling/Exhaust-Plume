"""Verify the externally supplied validation archives named by the handoff."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile

MANIFEST_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'validation' / 'corpus_intake_manifest_v1.json'
MANIFEST_ID = 'exhaust-plume-validation-corpus-intake-v1'
REQUIRED_ARCHIVES = (
  ('validation-corpus-v8', 'plume_validation_data_v8.zip'),
  ('mvp-validation-alignment-v1', 'plume_mvp_validation_alignment_v1.zip'),
)


@dataclass(frozen=True, slots=True)
class ArchiveCheck:
  archive_id: str
  filename: str
  path: str | None
  expected_sha256: str
  actual_sha256: str | None
  status: str
  member_count: int = 0
  unsafe_members: tuple[str, ...] = ()
  duplicate_members: tuple[str, ...] = ()
  errors: tuple[str, ...] = ()
####


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
  """Load and structurally validate the immutable intake manifest."""

  try:
    payload = json.loads(path.read_text(encoding='utf-8'))
  except (OSError, json.JSONDecodeError) as error:
    raise ValueError(f'could not read validation intake manifest: {error}') from error
  ####
  if not isinstance(payload, dict):
    raise ValueError('validation intake manifest must be a JSON object')
  ####
  manifest_id = payload.get('manifest_id')
  canonical_manifest = manifest_id is not None
  if canonical_manifest and manifest_id != MANIFEST_ID:
    raise ValueError(
      f'validation intake manifest must have manifest_id {MANIFEST_ID!r}'
    )
  ####
  archives = payload.get('archives')
  if not isinstance(archives, list):
    raise ValueError('validation intake manifest must contain an archives list')
  ####
  if len(archives) != len(REQUIRED_ARCHIVES):
    raise ValueError(
      'validation intake manifest must contain exactly the two required archives'
    )
  ####
  observed_ids: list[str] = []
  for index, archive in enumerate(archives):
    if not isinstance(archive, dict):
      raise ValueError(f'archives[{index}] must be a JSON object')
    ####
    archive_id = archive.get('archive_id')
    filename = archive.get('filename')
    digest = archive.get('sha256')
    retrieval = archive.get('retrieval')
    if not isinstance(archive_id, str) or not archive_id:
      raise ValueError(f'archives[{index}].archive_id must be non-empty')
    ####
    if not isinstance(filename, str) or not filename:
      raise ValueError(f'archives[{index}].filename must be non-empty')
    ####
    if not isinstance(digest, str) or len(digest) != 64 or any(
      character not in '0123456789abcdef' for character in digest
    ):
      raise ValueError(
        f'archives[{index}].sha256 must be a lowercase SHA-256 digest'
      )
    ####
    if canonical_manifest:
      if not isinstance(retrieval, dict):
        raise ValueError(f'archives[{index}].retrieval must be a JSON object')
      ####
      retrieval_status = retrieval.get('status')
      if not isinstance(retrieval_status, str) or not retrieval_status:
        raise ValueError(
          f'archives[{index}].retrieval.status must be non-empty'
        )
    ####
    observed_ids.append(archive_id)
  ####
  expected_ids = tuple(archive_id for archive_id, _filename in REQUIRED_ARCHIVES)
  if tuple(observed_ids) != expected_ids:
    raise ValueError(
      'validation intake manifest archive order/IDs must be '
      f'{expected_ids!r}'
    )
  ####
  if canonical_manifest:
    for index, (archive_id, expected_filename) in enumerate(REQUIRED_ARCHIVES):
      if archives[index]['filename'] != expected_filename:
        raise ValueError(
          f'archives[{index}] ({archive_id}) must name {expected_filename!r}'
        )
  ####
  return payload
####


def sha256_file(path: Path) -> str:
  """Return the lowercase SHA-256 digest of one file."""

  digest = sha256()
  with path.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
      digest.update(chunk)
    ####
  ####
  return digest.hexdigest()
####


def _unsafe_member(name: str) -> bool:
  normalized = name.replace('\\', '/')
  path = PurePosixPath(normalized)
  return (
    normalized.startswith('/')
    or '..' in path.parts
    or (path.parts and ':' in path.parts[0])
  )
####


def _zip_members(path: Path) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
  with ZipFile(path) as archive:
    names = tuple(info.filename for info in archive.infolist())
  ####
  counts: dict[str, int] = {}
  for name in names:
    counts[name] = counts.get(name, 0) + 1
  ####
  duplicates = tuple(sorted(name for name, count in counts.items() if count > 1))
  unsafe = tuple(sorted(name for name in names if _unsafe_member(name)))
  return len(names), unsafe, duplicates
####


def verify_archive(spec: Mapping[str, Any], path: Path) -> ArchiveCheck:
  """Verify one archive without extracting it."""

  archive_id = str(spec['archive_id'])
  filename = str(spec['filename'])
  expected = str(spec['sha256'])
  if not path.is_file():
    return ArchiveCheck(
      archive_id=archive_id,
      filename=filename,
      path=str(path),
      expected_sha256=expected,
      actual_sha256=None,
      status='missing',
      errors=('archive file does not exist',),
    )
  ####
  actual = sha256_file(path)
  if actual != expected:
    return ArchiveCheck(
      archive_id=archive_id,
      filename=filename,
      path=str(path),
      expected_sha256=expected,
      actual_sha256=actual,
      status='hash-mismatch',
      errors=('SHA-256 digest does not match the handoff manifest',),
    )
  ####
  try:
    member_count, unsafe, duplicates = _zip_members(path)
  except (BadZipFile, OSError) as error:
    return ArchiveCheck(
      archive_id=archive_id,
      filename=filename,
      path=str(path),
      expected_sha256=expected,
      actual_sha256=actual,
      status='invalid-zip',
      errors=(str(error),),
    )
  ####
  errors = tuple(
    item for item in (
      'archive contains unsafe member paths' if unsafe else None,
      'archive contains duplicate member names' if duplicates else None,
    )
    if item is not None
  )
  return ArchiveCheck(
    archive_id=archive_id,
    filename=filename,
    path=str(path),
    expected_sha256=expected,
    actual_sha256=actual,
    status='verified' if not errors else 'unsafe-archive',
    member_count=member_count,
    unsafe_members=unsafe,
    duplicate_members=duplicates,
    errors=errors,
  )
####


def verify_manifest(
    manifest: Mapping[str, Any],
    *,
    corpus_path: Path,
    alignment_path: Path,
) -> tuple[ArchiveCheck, ...]:
  """Verify the corpus and alignment archives against one manifest."""

  paths = {
    'validation-corpus-v8': corpus_path,
    'mvp-validation-alignment-v1': alignment_path,
  }
  checks = tuple(
    verify_archive(spec, paths[str(spec['archive_id'])])
    for spec in manifest['archives']
  )
  return checks
####


def _parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path, help='Path to plume_validation_data_v8.zip')
  parser.add_argument('--alignment', required=True, type=Path, help='Path to plume_mvp_validation_alignment_v1.zip')
  parser.add_argument('--manifest', default=MANIFEST_PATH, type=Path, help='Expected-digest manifest')
  parser.add_argument('--output', type=Path, help='Optional JSON report path')
  return parser
####


def main(argv: list[str] | None = None) -> int:
  arguments = _parser().parse_args(argv)
  manifest = load_manifest(arguments.manifest)
  checks = verify_manifest(
    manifest,
    corpus_path=arguments.corpus,
    alignment_path=arguments.alignment,
  )
  report = {
    'manifest_id': manifest.get('manifest_id'),
    'status': 'verified' if all(check.status == 'verified' for check in checks) else 'not-verified',
    'archives': [asdict(check) for check in checks],
  }
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if arguments.output is not None:
    arguments.output.write_text(serialized, encoding='utf-8')
  ####
  print(serialized, end='')
  return 0 if report['status'] == 'verified' else 1
####


if __name__ == '__main__':
  raise SystemExit(main(sys.argv[1:]))
####
