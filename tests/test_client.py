import pytest
from unittest.mock import MagicMock, patch
from stomp.exception import ConnectFailedException
from pigeon.client import Pigeon
from pigeon.exceptions import NoSuchTopicException
from pigeon import BaseMessage
import time
from math import floor


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
            connection_timeout=0.5,
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

    assert not pigeon_client._connected

    # Act
    pigeon_client.connect(username=username, password=password)

    # Assert
    pigeon_client._connection.connect.assert_called_with(
        username=username, passcode=password, wait=True
    )
    pigeon_client._logger.info.assert_called_with(expected_log)
    pigeon_client.subscribe.assert_not_called()

    assert pigeon_client._connected


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
    pigeon_client._logger.error = MagicMock()

    # Act & Assert
    with pytest.raises(
        ConnectFailedException, match="Could not connect to server: Connection failed"
    ):
        pigeon_client.connect(username=username, password=password)

    # Assert the logger was called the same number of times as the retry limit
    assert pigeon_client._logger.error.call_count == 1


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
        "version": pigeon_client._topic_versions[topic],
        "sent_at": "1",
    }
    # Arrange
    with patch("pigeon.client.time.time_ns", lambda: 1e6):
        pigeon_client._topics[topic] = MockMessage
        pigeon_client._connection.send = MagicMock()
        pigeon_client._connected = True

        # Act
        pigeon_client.send(topic, **data)

        # Assert
        pigeon_client._connection.send.assert_called_with(
            destination=topic, body=expected_serialized_data, headers=expected_headers
        )
        pigeon_client._logger.debug.assert_called_with(
            f"Sent data to {topic}: {MockMessage(**data)}"
        )


def test_send_headers(pigeon_client):
    pigeon_client.register_topic("test", MockMessage)
    pigeon_client._connection.send = MagicMock()
    pigeon_client._connected = True

    with patch("pigeon.client.time.time_ns", lambda: 1e6):
        pigeon_client._send("test", {"field1": "datas"}, headers={"test1": "this", "test2": "that"})

    pigeon_client._connection.send.assert_called_with(
        destination="test",
        body='{"field1":"datas"}',
        headers={
            "source": pigeon_client._name,
            "service": "test",
            "hostname": pigeon_client._hostname,
            "pid": pigeon_client._pid,
            "version": pigeon_client._topic_versions["test"],
            "sent_at": "1",
            "test1": "this",
            "test2": "that",
        },
    )



@pytest.mark.parametrize(
    "topic, data",
    [
        ("unknown_topic", {"key": "value"}),
    ],
    ids=["send-data-no-such-topic"],
)
def test_send_no_such_topic(pigeon_client, topic, data):
    pigeon_client._connected = True
    # Act & Assert
    with pytest.raises(NoSuchTopicException, match=f"Topic {topic} not defined."):
        pigeon_client.send(topic, **data)


@pytest.mark.timeout(2)
@pytest.mark.parametrize(
    "class_timeout, method_timeout, timeout",
    [(0, ..., 0), (0.5, ..., 0.5), (0, 0.3, 0.3), (None, 0.7, 0.7)],
)
@pytest.mark.parametrize("reason", ["connected", OSError, ConnectFailedException])
def test_send_timeout(
    mocker, pigeon_client, class_timeout, method_timeout, timeout, reason
):
    client = Pigeon(
        "test",
        host="localhost",
        port=61613,
        logger=mocker.MagicMock(),
        load_topics=False,
        connection_timeout=0.5,
        send_timeout=class_timeout,
    )
    client._connected = reason != "connected"
    client._ensure_topic_exists = mocker.MagicMock()
    client._connection = mocker.MagicMock()
    client.register_topic("some_topic", MockMessage)
    if not isinstance(reason, str) and issubclass(reason, Exception):
        client._connection.send.side_effect = reason
    start = time.time()
    with pytest.raises(TimeoutError):
        client.send("some_topic", timeout=method_timeout, field1="data")
    assert abs(time.time() - start - timeout) < 0.2


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

    # Act
    pigeon_client.subscribe(topic, callback)

    # Assert
    assert pigeon_client._callbacks[topic] == callback
    pigeon_client._connection.subscribe.assert_called_with(destination=topic, id=topic)
    pigeon_client._logger.info.assert_called_with(expected_log.format(callback))


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
    pigeon_client.subscribe.assert_any_call("topic1", callback)
    pigeon_client.subscribe.assert_any_call("topic2", callback)


def test_subscribe_all_no_topics(pigeon_client, mocker):
    pigeon_client._topics = {}
    pigeon_client._topic_versions = {}
    pigeon_client._connection = mocker.MagicMock()
    pigeon_client.subscribe = mocker.MagicMock()
    pigeon_client._connected = True

    callback = mocker.MagicMock()

    pigeon_client.subscribe_all(callback)
    pigeon_client._logger.warning.assert_called_once()


def test_handle_reconnect(pigeon_client, mocker):
    pigeon_client._connected = True

    pigeon_client.register_topic("topic3", MockMessage)
    pigeon_client.register_topic("topic4", MockMessage)

    topic2_cb = mocker.MagicMock()
    topic3_cb = mocker.MagicMock()

    pigeon_client.connect = mocker.MagicMock()
    pigeon_client._connection = mocker.MagicMock()

    pigeon_client.subscribe("topic2", topic2_cb)
    pigeon_client.subscribe("topic3", topic3_cb)

    pigeon_client.subscribe = mocker.MagicMock()

    pigeon_client._handle_reconnect()

    assert not pigeon_client._connected
    assert pigeon_client._callbacks == {}
    assert len(pigeon_client.subscribe.mock_calls) == 2

    pigeon_client.connect.assert_called_once_with()
    pigeon_client.subscribe.assert_any_call("topic2", topic2_cb)
    pigeon_client.subscribe.assert_any_call("topic3", topic3_cb)
    pigeon_client._logger.warning.assert_called_once_with(
        "Disconnected from broker. Attempting to reconnect..."
    )


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

    # Act
    pigeon_client.disconnect()

    # Assert
    pigeon_client._connection.disconnect.assert_called_once()
    pigeon_client._logger.info.assert_called_with("Disconnected from STOMP server.")
