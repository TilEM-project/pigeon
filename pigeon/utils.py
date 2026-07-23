import inspect
import logging
import os
from copy import copy
from importlib.metadata import packages_distributions, version
from logging.handlers import RotatingFileHandler
from multiprocessing import Queue

from logging_loki import LokiQueueHandler

from .exceptions import SignatureException

VERSIONS = {
    module: version(packages[0])
    for module, packages in packages_distributions().items()
}


def setup_logging(
    logger_name: str = None,
    log_level="INFO",
    log_levels: dict = None,
    log_file: str = None,
    log_file_max_bytes: int = 10_000_000,
    log_file_backups: int = 5,
):
    logger = logging.root if logger_name is None else logging.getLogger(logger_name)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(log_level.upper() if isinstance(log_level, str) else log_level)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    if log_file:
        fh = RotatingFileHandler(
            log_file, maxBytes=log_file_max_bytes, backupCount=log_file_backups
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    setup_loki(logger)

    # Apply env LOG_LEVEL first (fallback), then explicit log_levels so that
    # explicit configuration wins on any per-logger conflict.
    set_log_levels(logger)  # legacy env fallback (deprecated)
    for name, level in (log_levels or {}).items():
        _set_level(name, level, logger)

    return logger


def setup_loki(logger):
    if "LOKI_URL" not in os.environ:
        return
    logger.info("Initializing Loki log handler.")
    loki_handler = LokiQueueHandler(
        Queue(-1),
        url=os.environ.get("LOKI_URL"),
        tags=(
            dict(
                [val.strip() for val in tag.split(":")]
                for tag in os.environ.get("LOKI_TAGS").split(",")
            )
            if "LOKI_TAGS" in os.environ
            else None
        ),
        auth=(
            (os.environ.get("LOKI_USERNAME"), os.environ.get("LOKI_PASSWORD"))
            if "LOKI_USERNAME" in os.environ or "LOKI_PASSWORD" in os.environ
            else None
        ),
        version=os.environ.get("LOKI_VERSION", "1"),
    )
    loki_formatter = logging.Formatter("%(message)s")
    loki_handler.setFormatter(loki_formatter)
    logger.addHandler(loki_handler)


def _set_level(name, level, warn_logger):
    resolved = logging.getLevelNamesMapping().get(str(level).upper())
    if resolved is None:
        warn_logger.warning(
            f"Cannot set logger '{name}' to level '{level}' as it is not defined."
        )
        return
    logging.getLogger(name).setLevel(resolved)


def set_log_levels(logger):
    if "LOG_LEVEL" not in os.environ:
        return
    levels = [
        [s.strip() for s in level.split("=")]
        for level in os.environ.get("LOG_LEVEL").split(",")
    ]
    for name, level in levels:
        _set_level(name, level, logger)


def call_with_correct_args(func, *args, **kwargs):
    args = copy(args)
    kwargs = copy(kwargs)
    params = inspect.signature(func).parameters

    if True not in [
        param.kind == inspect._ParameterKind.VAR_POSITIONAL for param in params.values()
    ]:
        num_args = len(
            [
                None
                for param in params.values()
                if param.default == param.empty and param.kind != param.VAR_KEYWORD
            ]
        )
        if num_args > len(args):
            raise SignatureException(
                f"Function '{func}' requires {num_args} positional arguments, but only {len(args)} are available."
            )
        args = args[:num_args]

    if True not in [
        param.kind == inspect._ParameterKind.VAR_KEYWORD for param in params.values()
    ]:
        allowed_keys = [key for key, val in params.items() if val.default != val.empty]
        for key in list(kwargs.keys()):
            if key not in allowed_keys:
                del kwargs[key]

    return func(*args, **kwargs)


def get_version(msg_class):
    return VERSIONS.get(msg_class.__module__.split(".")[0], "[unknown]")
