"""Module which defines the Command Line Interface of the application.

This module uses the container available in the entrypoint module and overrides its settings before starting the app.
"""
import argparse
import typing
from collections import defaultdict

from wire.core.spec import create_container_from_specs
from structlog import get_logger

main_parser = argparse.ArgumentParser(prog="wire", add_help=True)
main_parser.add_argument(
    "spec",
    help="Application spec",
)
main_parser.add_argument(
    "--host",
    help="Host server shoud listen to",
    default=None,
)
main_parser.add_argument(
    "--port",
    help="Port server should listen to",
    type=int,
    default=None,
)
main_parser.add_argument(
    "--root-path",
    help="Root path used to serve the application",
    default=None,
)
main_parser.add_argument(
    "--debug",
    "-d",
    help="Enable debug mode",
    action="store_true",
)
main_parser.add_argument(
    "--no-debug",
    help="Disable debug mode",
    action="store_false",
)
main_parser.add_argument(
    "--config-file",
    "-c",
    help="Configuration file",
    default=None,
)
main_parser.add_argument(
    "--log-level",
    "-l",
    help="Logging level",
)
main_parser.add_argument(
    "--log-renderer",
    help="Logging renderer.  Possible choices: [console | json]",
)
main_parser.add_argument("--access-log", help="Enable access log", action="store_true")
main_parser.add_argument(
    "--no-access-log", help="Disable access log", action="store_false"
)
main_parser.add_argument(
    "--telemetry",
    help="Enable observability telemetry",
    action="store_true",
)
main_parser.add_argument(
    "--no-telemetry",
    help="Disable observability telemetry",
    action="store_false",
)
main_parser.add_argument(
    "--traces",
    help="Enable traces",
    action="store_true",
)
main_parser.add_argument(
    "--no-traces",
    help="Disable traces",
    action="store_false",
)
main_parser.add_argument(
    "--metrics",
    help="Enable metrics",
    action="store_true",
)
main_parser.add_argument(
    "--no-metrics",
    help="Disable metrics",
    action="store_false",
)
main_parser.add_argument(
    "--traces-exporter",
    help="Select traces exporter to use. Possible choices: [console | otlp]",
)
main_parser.set_defaults(
    debug=None,
    no_debug=None,
    telemetry=None,
    no_telemetry=None,
    access_log=None,
    no_access_log=None,
    metrics=None,
    no_metrics=None,
    traces=None,
    no_traces=None,
)


def run(*args: str) -> None:
    # Parse arguments
    if args:
        ns = main_parser.parse_args(args)
    else:
        ns = main_parser.parse_args()
    # Fetch spec argument
    spec = ns.spec
    # Initialize raw application settings to be parsed
    raw_settings: typing.Dict[str, typing.Any] = defaultdict(dict)
    # Only settings explicitely provided by user should be considered
    # FIXME: Using click would be much simpler...
    # It's possible to get the dict of arguments using
    # dict(ns._get_kwargs())
    # But then we still need to parse options like --opt/--no-opt
    if ns.host:
        raw_settings["server"]["host"] = ns.host
    if ns.port:
        raw_settings["server"]["port"] = ns.port
    if ns.root_path:
        raw_settings["server"]["root_path"] = ns.root_path
    if ns.debug is not None:
        raw_settings["server"]["debug"] = ns.debug
    if ns.no_debug is not None:
        raw_settings["server"]["debug"] = ns.no_debug
    if ns.telemetry is not None:
        raw_settings["telemetry"]["traces_enabled"] = ns.telemetry
        raw_settings["telemetry"]["metrics_enabled"] = ns.telemetry
    if ns.no_telemetry is not None:
        raw_settings["telemetry"]["traces_enabled"] = ns.no_telemetry
        raw_settings["telemetry"]["metrics_enabled"] = ns.no_telemetry
    if ns.metrics is not None:
        raw_settings["telemetry"]["metrics_enabled"] = ns.metrics
    if ns.no_metrics is not None:
        raw_settings["telemetry"]["metrics_enabled"] = ns.no_metrics
    if ns.traces is not None:
        raw_settings["telemetry"]["traces_enabled"] = ns.traces
    if ns.no_traces is not None:
        raw_settings["telemetry"]["traces_enabled"] = ns.no_traces
    if ns.traces_exporter is not None:
        raw_settings["telemetry"]["traces_exporter"] = ns.traces_exporter.lower()
    if ns.log_level:
        raw_settings["logging"]["level"] = ns.log_level.lower()
    if ns.log_renderer:
        raw_settings["logging"]["renderer"] = ns.log_renderer.lower()
    if ns.access_log is not None:
        raw_settings["logging"]["access_log"] = ns.debug
    if ns.no_access_log is not None:
        raw_settings["logging"]["access_log"] = ns.no_access_log
    # Create spec
    container = create_container_from_specs(
        spec, settings=raw_settings, config_file=ns.config_file
    )
    # Create a logger instance
    logger = get_logger()
    # Leave some info for debug
    logger.info(
        "Starting application with settings", **container.settings.dict(by_alias=True)
    )
    # Start the app
    container.run()
