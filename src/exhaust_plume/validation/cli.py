"""Command-line entry point for the declared simple-plume validity matrix."""

from __future__ import annotations

import argparse
from pathlib import Path

from exhaust_plume.validation.envelope import (
  default_validity_cases,
  evaluate_validity_matrix,
  write_validity_report_csv,
  write_validity_report_json,
)


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description='Evaluate the simple plume study-validity matrix.')
  parser.add_argument('--output-dir', type=Path, default=Path('validity-output'))
  args = parser.parse_args(argv)
  results = evaluate_validity_matrix(default_validity_cases())
  args.output_dir.mkdir(parents=True, exist_ok=True)
  write_validity_report_json(results, args.output_dir / 'validity_report.json')
  write_validity_report_csv(results, args.output_dir / 'validity_report.csv')
  print(f'Wrote {len(results)} validity cases to {args.output_dir}')
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
