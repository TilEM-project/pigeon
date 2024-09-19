from pigeon import utils
from pigeon.exceptions import SignatureException
import pytest
from unittest import mock
import os
import logging
from multiprocessing.queues import Queue


def test_get_message_hash():
    class TestMsg:
        attr_one: int
        attr_two: str
        attr_three: float

    assert utils.get_message_hash(TestMsg) == "e6b05f8920682eca0ba8b415c9fa7a7f248ddfce"


def test_not_enough_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    with pytest.raises(SignatureException):
        utils.call_with_correct_args(test_func, 1, 2, 3)


def test_equal_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    assert utils.call_with_correct_args(test_func, 1, 2, 3, 4) == (1, 2, 3, 4)


def test_args():
    def test_func(a, b, c, d):
        return a, b, c, d

    assert utils.call_with_correct_args(test_func, 1, 2, 3, 4, 5) == (1, 2, 3, 4)


def test_not_enough_kwargs():
    def test_func(a=1, b=2, c=3):
        return a, b, c

    assert utils.call_with_correct_args(test_func, a=10, b=11) == (10, 11, 3)


def test_no_args():
    def test_func():
        return True

    assert utils.call_with_correct_args(test_func, 1, 2, 3)


def test_both():
    def test_func(a, b, c, d=1, e=2):
        return a, b, c, d, e

    assert utils.call_with_correct_args(test_func, 1, 2, 3, 4, 5, d=10, e=11, f=12) == (
        1,
        2,
        3,
        10,
        11,
    )


def test_var_args():
    def test_func(a, b, *args):
        return a, b, args

    assert utils.call_with_correct_args(test_func, 1, 2, 3, 4) == (1, 2, (3, 4))


def test_var_kwargs():
    def test_func(a=1, b=2, **kwargs):
        return a, b, kwargs

    assert utils.call_with_correct_args(test_func, 1, 2, 3, a=10, c=11, d=12) == (
        10,
        2,
        {"c": 11, "d": 12},
    )


def test_both_var():
    def test_func(a, b, *args, c=1, d=2, **kwargs):
        return a, b, c, d, args, kwargs

    assert utils.call_with_correct_args(test_func, 1, 2, 3, 4, e=1, c=12, f=13) == (
        1,
        2,
        12,
        2,
        (3, 4),
        {"e": 1, "f": 13},
    )


def patch_env_vars(**vars):
    return mock.patch.dict(os.environ, **vars)


@pytest.fixture
def mock_loki(mocker):
    return mocker.patch("pigeon.utils.LokiQueueHandler")


def test_setup_logging_basic():
    logger = utils.setup_logging("test_logger")
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


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
            version=vars.get("LOKI_VERSION"),
        )
        assert logger.level == logging.WARN
        assert len(logger.handlers) == 2
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.handlers[1] == mock_loki()
