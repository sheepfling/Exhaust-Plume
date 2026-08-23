from argparse import ArgumentParser

from exhaust_plume.models.plume.run_plume_solve import ScriptOptions


def test_script_options_keep_plume_default_and_parse_float_gamma() -> None:
  parser = ArgumentParser()
  ScriptOptions.addArgumentsToParser(parser)
  options = ScriptOptions.fromNamespace(parser.parse_args(['--gamma', '1.4', '--num-plumes', '3']))

  assert options.num_plumes == 3
  assert options.gamma == 1.4
####
