import time
from threading import Thread

import pytest

from pigeon import BaseMessage, PigeonScript
from pigeon.exceptions import NoSuchTopicException
from pigeon.script import NotReceived


class MockMessage(BaseMessage):
    field1: str


def make_client(mocker, **kwargs):
    client = PigeonScript(
        "test",
        host="localhost",
        port=61613,
        logger=mocker.MagicMock(),
        load_topics=False,
        connection_timeout=0.5,
        **kwargs,
    )
    client.register_topics({"topic1": MockMessage, "topic2": MockMessage})
    client._connection = mocker.MagicMock()
    return client


@pytest.fixture
def client(mocker):
    return make_client(mocker)


def test_import_from_package():
    from pigeon import PigeonScript as imported

    assert imported is PigeonScript


def test_init_state(client):
    assert client._script_callbacks == {}
    assert client._messages == {}
    # base class callbacks must not be clobbered by the subclass
    assert client._callbacks == {}


def test_subscribe_registers_internal_callback(client):
    client.subscribe("topic1")

    client._connection.subscribe.assert_called_once_with(destination="topic1", id="topic1")
    assert client._callbacks["topic1"] == client._callback
    assert "topic1" not in client._script_callbacks


def test_subscribe_with_callback(client, mocker):
    callback = mocker.MagicMock(__name__="callback")

    client.subscribe("topic1", callback)

    assert client._callbacks["topic1"] == client._callback
    assert client._script_callbacks["topic1"] == [callback]


def test_subscribe_multiple_callbacks_one_topic(client, mocker):
    cb1 = mocker.MagicMock(__name__="cb1")
    cb2 = mocker.MagicMock(__name__="cb2")

    client.subscribe("topic1", cb1)
    client.subscribe("topic1", cb2)

    assert client._script_callbacks["topic1"] == [cb1, cb2]
    # the underlying connection is only subscribed once per topic
    client._connection.subscribe.assert_called_once()


def test_subscribe_no_such_topic(client):
    with pytest.raises(NoSuchTopicException):
        client.subscribe("nope")


def test_subscribe_all_uses_internal_callback(client):
    client.subscribe_all()

    assert client._callbacks == {
        "topic1": client._callback,
        "topic2": client._callback,
    }
    assert client._script_callbacks == {}


def test_subscribe_all_with_callback(client, mocker):
    callback = mocker.MagicMock(__name__="callback")

    client.subscribe_all(callback)

    assert client._script_callbacks == {
        "topic1": [callback],
        "topic2": [callback],
    }


def test_remove_callback(client, mocker):
    cb1 = mocker.MagicMock(__name__="cb1")
    cb2 = mocker.MagicMock(__name__="cb2")
    client.subscribe("topic1", cb1)
    client.subscribe("topic1", cb2)

    client.remove_callback("topic1", cb1)

    assert client._script_callbacks["topic1"] == [cb2]


def test_remove_callback_unknown_topic(client, mocker):
    with pytest.raises(AssertionError):
        client.remove_callback("topic1", mocker.MagicMock())


def test_callback_stores_message_and_calls_callbacks(client, mocker):
    calls = []
    client.subscribe("topic1", lambda msg: calls.append(msg))
    client.subscribe("topic1", lambda msg, topic, headers: calls.append((topic, headers)))
    message = MockMessage(field1="value")

    client._callback(message, "topic1", {"header": "a"})

    assert client._messages["topic1"] is message
    assert calls == [message, ("topic1", {"header": "a"})]


def test_callback_allows_removal_during_iteration(client):
    received = []

    def callback(msg):
        received.append(msg)
        client.remove_callback("topic1", callback)

    client.subscribe("topic1", callback)
    message = MockMessage(field1="value")

    client._callback(message, "topic1", {})
    client._callback(message, "topic1", {})

    assert received == [message]
    assert client._script_callbacks["topic1"] == []


def test_callback_no_registered_callbacks(client):
    message = MockMessage(field1="value")

    client._callback(message, "topic1", {})

    assert client.get_message("topic1") is message


def test_handle_message_routes_to_script_callback(client):
    from stomp.utils import Frame

    received = []
    client.subscribe("topic1", lambda msg: received.append(msg))

    client._handle_message(
        Frame("MESSAGE", {"destination": "topic1"}, '{"field1":"value"}')
    )

    assert client.get_message("topic1") == MockMessage(field1="value")
    assert received == [MockMessage(field1="value")]


def test_get_message_not_received(client):
    with pytest.raises(NotReceived, match="No message on topic topic1"):
        client.get_message("topic1")


@pytest.mark.timeout(5)
def test_wait_for_message(client):
    message = MockMessage(field1="value")

    def send_later():
        time.sleep(0.2)
        client._callback(message, "topic1", {})

    Thread(target=send_later).start()

    assert client.wait_for_message("topic1", timeout=3) is message
    assert client._script_callbacks["topic1"] == []


@pytest.mark.timeout(5)
def test_wait_for_message_with_filter(client):
    wanted = MockMessage(field1="wanted")

    def send_later():
        time.sleep(0.2)
        client._callback(MockMessage(field1="other"), "topic1", {})
        time.sleep(0.2)
        client._callback(wanted, "topic1", {})

    Thread(target=send_later).start()

    result = client.wait_for_message(
        "topic1", timeout=3, filter=lambda msg: msg.field1 == "wanted"
    )

    assert result is wanted
    assert client._script_callbacks["topic1"] == []


@pytest.mark.timeout(5)
def test_wait_for_message_timeout(client):
    start = time.time()

    with pytest.raises(TimeoutError, match="within 0.5 seconds"):
        client.wait_for_message("topic1", timeout=0.5)

    assert 0.4 < time.time() - start < 2
    assert client._script_callbacks["topic1"] == []


@pytest.mark.timeout(5)
def test_wait_for_message_timeout_filter_never_matches(client):
    def send_later():
        time.sleep(0.1)
        client._callback(MockMessage(field1="other"), "topic1", {})

    Thread(target=send_later).start()

    with pytest.raises(TimeoutError):
        client.wait_for_message("topic1", timeout=0.5, filter=lambda msg: False)


def test_wait_for_message_no_such_topic(client):
    with pytest.raises(NoSuchTopicException):
        client.wait_for_message("nope", timeout=0.1)
