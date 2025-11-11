from pigeon import utils
import pytest
from unittest import mock
import os
import logging
from multiprocessing.queues import Queue


def patch_env_vars(**vars):
    return mock.patch.dict(os.environ, **vars)


@pytest.fixture
def mock_loki(mocker):
    return mocker.patch("pigeon.utils.LokiQueueHandler")


def test_setup_logging_basic():
    logger = utils.setup_logging("test_logger")
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.NOTSET
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_setup_logging_root():
    logger = utils.setup_logging()

    assert logger is logging.root


@pytest.mark.parametrize(
    "vars,tags,auth",
    [
        (dict(LOKI_URL="http://a.test.url:1234/", LOKI_VERSION="1"), None, None),
        (
            dict(
                LOKI_URL="https://a.test.secure.url:4321/",
                LOKI_USERNAME="user",
                LOKI_VERSION="2",
            ),
            None,
            ("user", None),
        ),
        (
            dict(LOKI_URL="a.url", LOKI_USERNAME="me", LOKI_PASSWORD="passed"),
            None,
            ("me", "passed"),
        ),
        (
            dict(LOKI_URL="a.url", LOKI_TAGS="tag one: one, tag two : three"),
            {"tag one": "one", "tag two": "three"},
            None,
        ),
    ],
)
def test_setup_logging_loki(request, vars, tags, auth, mock_loki):
    with patch_env_vars(**vars):
        logger = utils.setup_logging(f"loki_test_{request.node.name}", logging.WARN)
        mock_loki.assert_called_once()
        assert len(mock_loki.mock_calls[0].args) == 1
        assert isinstance(mock_loki.mock_calls[0].args[0], Queue)
        assert mock_loki.mock_calls[0].kwargs == dict(
            url=vars.get("LOKI_URL"),
            tags=tags,
            auth=auth,
            version=vars.get("LOKI_VERSION", "1"),
        )
        assert logger.level == logging.WARN
        assert logger.handlers[0].level == logging.NOTSET
        assert len(logger.handlers) == 2
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.handlers[1] == mock_loki()


@pytest.mark.parametrize(
    "var, levels",
    [
        ("test.module.one=DEBUG", {"test.module.one": 10}),
        (
            "another.module=INFO,that.thing=WARNING",
            {"another.module": 20, "that.thing": 30},
        ),
        (
            " the.last.module = CRITICAL , the.final.package = ERROR ",
            {"the.last.module": 50, "the.final.package": 40},
        ),
    ],
)
def test_setup_logging_levels(var, levels):
    with patch_env_vars(LOG_LEVEL=var):
        utils.setup_logging("")
        for logger, level in levels.items():
            assert logging.getLogger(logger).level == level
