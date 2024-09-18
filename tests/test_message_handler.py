import pytest
from unittest.mock import MagicMock, patch
from pigeon.client import Pigeon
from pydantic import ValidationError


@pytest.fixture
def pigeon_client():
    with patch("pigeon.utils.setup_logging") as mock_logging:
        with patch("pigeon.client.stomp"):
            client = Pigeon(
                "test",
                host="localhost",
                port=61613,
                logger=mock_logging.Logger(),
                load_topics=False,
            )
            yield client


def test_one_arg(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "hash": "abcd",
    }

    mock_message = MagicMock()

    def callback(msg):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()

    pigeon_client._connection = MagicMock()
    pigeon_client._topics["test.msg"] = mock_message
    pigeon_client._hashes["test.msg"] = "abcd"
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_two_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "hash": "abcde",
    }

    mock_message = MagicMock()

    def callback(msg, topic):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"

    pigeon_client._connection = MagicMock()
    pigeon_client._topics["test.msg"] = mock_message
    pigeon_client._hashes["test.msg"] = "abcde"
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_three_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "hash": "123abc",
    }

    mock_message = MagicMock()

    def callback(msg, topic, headers):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"
        assert headers == mock_stomp_message.headers

    pigeon_client._connection = MagicMock()
    pigeon_client._topics["test.msg"] = mock_message
    pigeon_client._hashes["test.msg"] = "123abc"
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_var_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "hash": "xyz987",
    }

    mock_message = MagicMock()

    def callback(*args):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert len(args) == 3
        assert args[0] == mock_message.deserialize()
        assert args[1] == "test.msg"
        assert args[2] == mock_stomp_message.headers

    pigeon_client._connection = MagicMock()
    pigeon_client._topics["test.msg"] = mock_message
    pigeon_client._hashes["test.msg"] = "xyz987"
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def create_mock_message(body="", **headers):
    return MagicMock(body=body, headers=headers)


def test_topic_does_not_exist(pigeon_client):
    mock_message = create_mock_message(subscription="not.a.real.message")

    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Received a message on an unregistered topic: not.a.real.message"
    )


def test_hash_mismatch(pigeon_client):
    mock_message = create_mock_message(subscription="test", hash="abc1")

    pigeon_client._topics["test"] = None
    pigeon_client._hashes["test"] = "abcd"
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Received a message on topic 'test' with an incorrect hash: abc1. Expected: abcd"
    )


def test_validation_error(pigeon_client):
    mock_message = create_mock_message(subscription="test", hash="abc123")
    mock_msg_def = MagicMock()
    mock_msg_def.deserialize.side_effect = ValidationError.from_exception_data(
        title="Test", line_errors=[]
    )

    pigeon_client._topics["test"] = mock_msg_def
    pigeon_client._hashes["test"] = "abc123"
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Failed to deserialize message on topic 'test' with error:\n0 validation errors for Test\n"
    )


def test_no_callback(pigeon_client):
    mock_message = create_mock_message(subscription="test", hash="4321")

    pigeon_client._topics["test"] = MagicMock()
    pigeon_client._hashes["test"] = "4321"
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "No callback for message received on topic 'test'."
    )


def test_bad_signature(pigeon_client):
    mock_message = create_mock_message(subscription="test", hash="lmnop")
    callback = lambda a, b, c, d: None

    pigeon_client._topics["test"] = MagicMock()
    pigeon_client._hashes["test"] = "lmnop"
    pigeon_client.subscribe("test", callback)
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback signature for topic 'test' not acceptable. Call failed with error:\nFunction '{callback}' requires 4 positional arguments, but only 3 are available."
    )


def test_callback_exception(pigeon_client):
    mock_message = create_mock_message(subscription="test", hash="987654321")

    pigeon_client._topics["test"] = MagicMock()
    pigeon_client._hashes["test"] = "987654321"
    pigeon_client.subscribe(
        "test", MagicMock(side_effect=RecursionError("This is a test error."))
    )
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback for topic 'test' failed with error:", exc_info=True
    )
