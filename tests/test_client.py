import pytest
from unittest.mock import MagicMock, patch
from stomp.exception import ConnectFailedException
from pigeon.client import Pigeon
from pigeon.exceptions import NoSuchTopicException
from pigeon import BaseMessage


class MockMessage(BaseMessage):
    field1: str


@pytest.fixture
def pigeon_client():
    with patch("pigeon.utils.setup_logging") as mock_logging:
        topics = {"topic1": MockMessage, "topic2": MockMessage}
        client = Pigeon(
            "test",
            host="localhost",
            port=61613,
            logger=mock_logging.Logger(),
            load_topics=False,
        )
        client.register_topics(topics)
        yield client


@pytest.mark.parametrize(
    "username, password, expected_log",
    [
        (None, None, "Connected to STOMP server."),
        ("user", "pass", "Connected to STOMP server."),
    ],
    ids=["no-auth", "with-auth"],
)
def test_connect(pigeon_client, username, password, expected_log):
    # Arrange
    pigeon_client._connection.connect = MagicMock()
    pigeon_client.subscribe = MagicMock()
    pigeon_client._announce = MagicMock()

    # Act
    pigeon_client.connect(username=username, password=password)

    # Assert
    pigeon_client._connection.connect.assert_called_with(
        username=username, passcode=password, wait=True
    )
    pigeon_client._logger.info.assert_called_with(expected_log)
    pigeon_client.subscribe.assert_called_with(
        "&_request_state", pigeon_client._update_state
    )
    pigeon_client._announce.assert_called()


@pytest.mark.parametrize(
    "username, password",
    [
        (None, None),
        ("user", "pass"),
    ],
    ids=["connect-fail-no-auth", "connect-fail-with-auth"],
)
def test_connect_failure(pigeon_client, username, password):
    # Arrange
    pigeon_client._connection.connect = MagicMock(
        side_effect=ConnectFailedException("Connection failed")
    )
    retry_limit = 1
    pigeon_client._logger.error = MagicMock()

    # Act & Assert
    with pytest.raises(
        ConnectFailedException, match="Could not connect to server: Connection failed"
    ):
        pigeon_client.connect(
            username=username, password=password, retry_limit=retry_limit
        )

    # Assert the logger was called the same number of times as the retry limit
    assert pigeon_client._logger.error.call_count == retry_limit


@pytest.mark.parametrize(
    "topic, data, expected_serialized_data",
    [
        ("topic1", {"field1": "value"}, '{"field1":"value"}'),
    ],
    ids=["send-data"],
)
def test_send(pigeon_client, topic, data, expected_serialized_data):
    expected_headers = {
        "source": pigeon_client._name,
        "service": "test",
        "hostname": pigeon_client._hostname,
        "pid": pigeon_client._pid,
        "hash": pigeon_client._hashes["topic1"],
        "sent_at": "1",
    }
    # Arrange
    with patch("pigeon.client.time.time_ns", lambda: 1e6):
        pigeon_client._topics[topic] = MockMessage
        pigeon_client._connection.send = MagicMock()

        # Act
        pigeon_client.send(topic, **data)

        # Assert
        pigeon_client._connection.send.assert_called_with(
            destination=topic, body=expected_serialized_data, headers=expected_headers
        )
        pigeon_client._logger.debug.assert_called_with(
            f"Sent data to {topic}: {expected_serialized_data}"
        )


@pytest.mark.parametrize(
    "topic, data",
    [
        ("unknown_topic", {"key": "value"}),
    ],
    ids=["send-data-no-such-topic"],
)
def test_send_no_such_topic(pigeon_client, topic, data):
    # Act & Assert
    with pytest.raises(NoSuchTopicException, match=f"Topic {topic} not defined."):
        pigeon_client.send(topic, **data)


@pytest.mark.parametrize(
    "topic, callback_name, expected_log",
    [
        ("topic1", "callback", "Subscribed to topic1 with {}."),
    ],
    ids=["subscribe-new-topic"],
)
def test_subscribe(pigeon_client, topic, callback_name, expected_log):
    # Arrange
    pigeon_client._topics[topic] = MockMessage
    callback = MagicMock(__name__=callback_name)
    pigeon_client._connection.subscribe = MagicMock()
    pigeon_client._update_state = MagicMock()

    # Act
    pigeon_client.subscribe(topic, callback)

    # Assert
    assert pigeon_client._callbacks[topic] == callback
    pigeon_client._connection.subscribe.assert_called_with(destination=topic, id=topic)
    pigeon_client._logger.info.assert_called_with(expected_log.format(callback))
    pigeon_client._update_state.assert_called()


@pytest.mark.parametrize(
    "topic",
    [
        ("unknown_topic"),
    ],
    ids=["subscribe-no-such-topic"],
)
def test_subscribe_no_such_topic(pigeon_client, topic):
    # Arrange
    callback = MagicMock()

    # Act & Assert
    with pytest.raises(NoSuchTopicException, match=f"Topic {topic} not defined."):
        pigeon_client.subscribe(topic, callback)


def test_subscribe_all(pigeon_client, mocker):
    pigeon_client._connection = mocker.MagicMock()
    pigeon_client.subscribe = mocker.MagicMock()

    callback = mocker.MagicMock()

    pigeon_client.subscribe_all(callback)

    assert len(pigeon_client.subscribe.mock_calls) == 2
    pigeon_client.subscribe.assert_any_call("topic1", callback, send_update=False)
    pigeon_client.subscribe.assert_any_call("topic2", callback, send_update=False)


def test_subscribe_all_with_core(pigeon_client, mocker):
    pigeon_client._connection = mocker.MagicMock()
    pigeon_client.subscribe = mocker.MagicMock()

    callback = mocker.MagicMock()

    pigeon_client.subscribe_all(callback, include_core=True)

    assert len(pigeon_client.subscribe.mock_calls) == 4
    pigeon_client.subscribe.assert_any_call("topic1", callback, send_update=False)
    pigeon_client.subscribe.assert_any_call("topic2", callback, send_update=False)
    pigeon_client.subscribe.assert_any_call("&_announce_connection", callback, send_update=False)
    pigeon_client.subscribe.assert_any_call("&_update_state", callback, send_update=False)


@pytest.mark.parametrize(
    "topic, expected_log",
    [
        ("topic1", "Unsubscribed from topic1."),
    ],
    ids=["unsubscribe-existing-topic"],
)
def test_unsubscribe(pigeon_client, topic, expected_log):
    # Arrange
    pigeon_client._callbacks[topic] = ["topic1"]
    pigeon_client._connection.unsubscribe = MagicMock()

    # Act
    pigeon_client.unsubscribe(topic)

    # Assert
    assert topic not in pigeon_client._callbacks
    pigeon_client._connection.unsubscribe.assert_called_with(id=topic)
    pigeon_client._logger.info.assert_called_with(expected_log)


def test_disconnect(pigeon_client):
    # Arrange
    pigeon_client._connection.is_connected = MagicMock(return_value=True)
    pigeon_client._connection.disconnect = MagicMock()
    pigeon_client._announce = MagicMock()

    # Act
    pigeon_client.disconnect()

    # Assert
    pigeon_client._connection.disconnect.assert_called_once()
    pigeon_client._logger.info.assert_called_with("Disconnected from STOMP server.")
    pigeon_client._announce.assert_called_with(connected=False)
