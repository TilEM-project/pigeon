import logging
import inspect
from copy import copy

from .exceptions import SignatureException


def setup_logging(logger_name: str, log_level: int = logging.INFO):
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
    return logger


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
