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
        "version": "v1.2.3",
    }

    mock_message = MagicMock()

    def callback(msg):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()

    pigeon_client._connection = MagicMock()
    pigeon_client.register_topic("test.msg", mock_message, "v1.2.3")
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_two_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "version": "v1.2.3",
    }

    mock_message = MagicMock()

    def callback(msg, topic):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"

    pigeon_client._connection = MagicMock()
    pigeon_client.register_topic("test.msg", mock_message, "v1.2.3")
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_three_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "version": "v1.2.3",
    }

    mock_message = MagicMock()

    def callback(msg, topic, headers):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"
        assert headers == mock_stomp_message.headers

    pigeon_client._connection = MagicMock()
    pigeon_client.register_topic("test.msg", mock_message, "v1.2.3")
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_var_args(pigeon_client):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
        "version": "v1.2.3",
    }

    mock_message = MagicMock()

    def callback(*args):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert len(args) == 3
        assert args[0] == mock_message.deserialize()
        assert args[1] == "test.msg"
        assert args[2] == mock_stomp_message.headers

    pigeon_client._connection = MagicMock()
    pigeon_client.register_topic("test.msg", mock_message, "v1.2.3")
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


def test_version_mismatch(pigeon_client):
    mock_message = create_mock_message(subscription="test", version="v0.1.1")

    pigeon_client.register_topic("test", lambda x: x, "v0.1.0")
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Received a message on topic 'test' with an incorrect version v0.1.1. Version should be v0.1.0"
    )


def test_validation_error(pigeon_client):
    mock_message = create_mock_message(subscription="test", version="v0.1.0")
    mock_msg_def = MagicMock()
    mock_msg_def.deserialize.side_effect = ValidationError.from_exception_data(
        title="Test", line_errors=[]
    )

    pigeon_client.register_topic("test", mock_msg_def, "v0.1.0")
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Failed to deserialize message on topic 'test' with error:\n0 validation errors for Test\n"
    )


def test_no_callback(pigeon_client):
    mock_message = create_mock_message(subscription="test", version="v0.1.0")

    pigeon_client.register_topic("test", MagicMock(), "v0.1.0")
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "No callback for message received on topic 'test'."
    )


def test_bad_signature(pigeon_client):
    mock_message = create_mock_message(subscription="test", version="v0.1.0")
    callback = lambda a, b, c, d: None

    pigeon_client.register_topic("test", MagicMock(), "v0.1.0")
    pigeon_client.subscribe("test", callback)
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback signature for topic 'test' not acceptable. Call failed with error:\nFunction '{callback}' requires 4 positional arguments, but only 3 are available."
    )


def test_callback_exception(pigeon_client):
    mock_message = create_mock_message(subscription="test", version="v0.1.0")

    pigeon_client.register_topic("test", MagicMock(), "v0.1.0")
    pigeon_client.subscribe(
        "test", MagicMock(side_effect=RecursionError("This is a test error."))
    )
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback for topic 'test' failed with error:", exc_info=True
    )
