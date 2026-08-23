"""Command-line entry point for the visual-product MVP."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from exhaust_plume.products.workflow_visual import (
  build_sectioned_tube_mesh,
  evaluate_visual_definition,
  load_straight_visual_definition,
  render_visual_preview,
  write_visual_mesh_json,
  write_visual_obj,
  write_visual_result_json,
)


def main(argv: list[str] | None = None) -> int:
  parser = ArgumentParser(description='Render and export a straight sectioned-tube visual product.')
  parser.add_argument('--config', required=True, type=Path, help='JSON straight visual definition.')
  parser.add_argument('--output-dir', default=Path('visual-output'), type=Path)
  parser.add_argument('--maximum-section-count', type=int, default=None)
  parser.add_argument('--ring-segments', type=int, default=24)
  parser.add_argument('--channel', default=None, help='Optional section channel used for preview coloring.')
  parser.add_argument('--time-s', type=float, default=0.0)
  parser.add_argument('--no-preview', action='store_true', help='Skip the optional Matplotlib PNG preview.')
  args = parser.parse_args(argv)

  definition = load_straight_visual_definition(args.config)
  result = evaluate_visual_definition(
    definition,
    maximum_section_count=args.maximum_section_count,
    requested_channels=(args.channel,) if args.channel else (),
    time_s=args.time_s,
  )
  mesh = build_sectioned_tube_mesh(result, radial_segments=args.ring_segments)
  output_dir: Path = args.output_dir
  outputs = (
    write_visual_result_json(result, output_dir / 'visual_result.json'),
    write_visual_mesh_json(mesh, output_dir / 'visual_mesh.json'),
    write_visual_obj(mesh, output_dir / 'visual_mesh.obj'),
  )
  if not args.no_preview:
    outputs += (render_visual_preview(result, output_dir / 'visual_preview.png', channel=args.channel, radial_segments=args.ring_segments),)
  ####
  for output in outputs:
    print(output)
  ####
  return 0
####


if __name__ == '__main__':
  raise SystemExit(main())
####
