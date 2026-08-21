from exhaust_plume.log.log import configureLogging


def test_packaged_default_logging_configuration_loads() -> None:
  assert configureLogging()
