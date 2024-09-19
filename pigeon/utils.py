import logging
import inspect
from copy import copy
import hashlib
from typing import Callable
import os
from logging_loki import LokiQueueHandler
from multiprocessing import Queue

from .exceptions import SignatureException


def setup_logging(logger_name: str, log_level: int = logging.INFO):
    logger = logging.getLogger(logger_name)
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)
    logger.setLevel(log_level)
    if "LOKI_URL" in os.environ:
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
            version=os.environ.get("LOKI_VERSION"),
        )
        loki_formatter = logging.Formatter("%(message)s")
        loki_handler.setFormatter(loki_formatter)
        logger.addHandler(loki_handler)
    return logger


def get_message_hash(msg_cls: Callable):
    hash = hashlib.sha1()
    hash.update(inspect.getsource(msg_cls).encode("utf8"))
    return hash.hexdigest()


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
