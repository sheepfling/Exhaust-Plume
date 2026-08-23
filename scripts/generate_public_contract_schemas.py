from __future__ import annotations

import argparse

from exhaust_plume.contracts.schema_v1 import export_public_schemas


def main() -> None:
  parser = argparse.ArgumentParser(description='Export versioned public plume contract schemas.')
  parser.add_argument('directory', nargs='?', default='schemas')
  arguments = parser.parse_args()
  for path in export_public_schemas(arguments.directory):
    print(path)


if __name__ == '__main__':
  main()
