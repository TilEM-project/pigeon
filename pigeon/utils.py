import logging
from logging import _nameToLevel
import inspect
from copy import copy
import hashlib
from typing import Callable
import os
from logging_loki import LokiQueueHandler
from multiprocessing import Queue
from importlib.metadata import packages_distributions, version

from .exceptions import SignatureException


DISTRIBUTIONS = {
    module: packages[0] for module, packages in packages_distributions().items()
}


def setup_logging(logger_name: str = None, log_level: int = logging.INFO):
    logger = logging.root if logger_name is None else logging.getLogger(logger_name)
    logger.setLevel(log_level)
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    setup_loki(logger)
    set_log_levels(logger)

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


def set_log_levels(logger):
    if "LOG_LEVEL" not in os.environ:
        return
    levels = [
        [s.strip() for s in level.split("=")]
        for level in os.environ.get("LOG_LEVEL").split(",")
    ]
    for name, level in levels:
        try:
            logging.getLogger(name).setLevel(_nameToLevel[level])
        except KeyError:
            logger.warning(
                f"Cannot set logger '{name}' to level '{level}' as it is not defined."
            )


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
    return DISTRIBUTIONS.get(msg_class.__module__.split(".")[0], "[unknown]")
