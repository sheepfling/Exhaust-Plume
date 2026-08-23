"""Command-line entry point for the lookup-backed signature MVP."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from exhaust_plume.products.signature import (
  evaluate_signature_table_asset,
  load_signature_table_asset,
  load_spectral_signature_request,
  render_signature_plots,
  write_signature_result_csv,
  write_signature_result_json,
)
from exhaust_plume.contracts import TimeModel
from exhaust_plume.providers.signature_table import SignatureTableConfiguration


def main(argv: list[str] | None = None) -> int:
  parser = ArgumentParser(description='Evaluate and plot a lookup-backed spectral signature.')
  parser.add_argument('--asset', required=True, type=Path, help='JSON signature-table asset.')
  parser.add_argument('--request', required=True, type=Path, help='JSON spectral signature request.')
  parser.add_argument('--output-dir', default=Path('signature-output'), type=Path)
  parser.add_argument('--time-s', type=float, default=0.0)
  parser.add_argument(
    '--time-model',
    choices=(TimeModel.STEADY.value, TimeModel.PRESCRIBED_TRANSIENT.value),
    default=TimeModel.STEADY.value,
    help='Time claim for a static or prescribed time-sliced asset.',
  )
  parser.add_argument('--allow-extrapolation', action='store_true')
  parser.add_argument('--no-plots', action='store_true', help='Skip optional Matplotlib plots.')
  args = parser.parse_args(argv)

  definition = load_signature_table_asset(args.asset)
  request = load_spectral_signature_request(args.request)
  configuration = SignatureTableConfiguration(
    allow_extrapolation=args.allow_extrapolation,
    time_model=TimeModel(args.time_model),
  )
  result = evaluate_signature_table_asset(
    definition,
    request,
    configuration=configuration,
    time_s=args.time_s,
  )
  output_dir: Path = args.output_dir
  outputs = (
    write_signature_result_json(result, output_dir / 'signature_result.json'),
    write_signature_result_csv(definition, request, result, output_dir / 'signature_result.csv'),
  )
  if not args.no_plots:
    outputs += render_signature_plots(definition, request, result, output_dir)
  for output in outputs:
    print(output)
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
