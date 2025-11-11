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


@pytest.mark.parametrize("include_topic", [False, True])
@pytest.mark.parametrize("include_headers", [False, True])
def test_message_handler(pigeon_client, include_topic, include_headers):
    mock_stomp_message = MagicMock()
    mock_stomp_message.headers = {
        "subscription": "test.msg",
    }

    mock_message = MagicMock()

    def callback(msg, *args):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        args = list(args)
        if include_topic:
            topic = args.pop(0)
            assert topic == "test.msg"
        if include_headers:
            headers = args.pop(0)
            assert headers == mock_stomp_message.headers

    pigeon_client._connection = MagicMock()
    pigeon_client.register_topic("test.msg", mock_message)
    pigeon_client.subscribe(
        "test.msg",
        callback,
        include_topic=include_topic,
        include_headers=include_headers,
    )

    pigeon_client._handle_message(mock_stomp_message)
    pigeon_client._logger.warning.assert_not_called()


def create_mock_message(body="", **headers):
    return MagicMock(body=body, headers=headers)


def test_topic_does_not_exist(pigeon_client):
    mock_message = create_mock_message(subscription="not.a.real.message")

    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Received a message on an unregistered topic: not.a.real.message"
    )


def test_validation_error(pigeon_client):
    mock_message = create_mock_message(subscription="test")
    mock_msg_def = MagicMock()
    mock_msg_def.deserialize.side_effect = ValidationError.from_exception_data(
        title="Test", line_errors=[]
    )

    pigeon_client.register_topic("test", mock_msg_def)
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Failed to deserialize message on topic 'test' due to error:\n0 validation errors for Test\nInstalled message version is [unknown] and received message version is [undefined]"
    )


def test_no_callback(pigeon_client):
    mock_message = create_mock_message(subscription="test")

    pigeon_client.register_topic("test", MagicMock())
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "No callback for message received on topic 'test'."
    )


def test_callback_exception(pigeon_client):
    mock_message = create_mock_message(subscription="test")

    pigeon_client.register_topic("test", MagicMock())
    pigeon_client.subscribe(
        "test",
        MagicMock(side_effect=RecursionError("This is a test error.")),
    )
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback for topic 'test' failed with error:", exc_info=True
    )
