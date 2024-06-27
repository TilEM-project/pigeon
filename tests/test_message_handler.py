import pytest
from unittest.mock import MagicMock, patch
from pigeon.client import Pigeon


@pytest.fixture
def pigeon_client():
    with patch("pigeon.logging.setup_logging") as mock_logging:
        client = Pigeon(
            "test", host="localhost", port=61613, logger=mock_logging.Logger()
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
