import pytest
from pigeon.client import Pigeon
from pydantic import ValidationError
from unittest.mock import MagicMock


@pytest.fixture
def mock_message(mocker):
    mock_message = mocker.MagicMock()
    return mock_message


@pytest.fixture
def pigeon_client(mocker, mock_message):
    mock_logging = mocker.MagicMock()
    mocker.patch("pigeon.client.stomp")
    client = Pigeon(
        "test",
        host="localhost",
        port=61613,
        logger=mock_logging.Logger(),
        load_topics=False,
    )
    client._connection = mocker.MagicMock()
    client.register_topic("test.msg", mock_message)
    yield client


@pytest.fixture
def mock_stomp_message(mocker):
    mock_stomp_message = mocker.MagicMock()
    mock_stomp_message.headers = {"subscription": "foo", "destination": "test.msg"}
    return mock_stomp_message


@pytest.mark.parametrize("prefix", ["", "p1/", "prefix2."])
def test_handle_prefix(pigeon_client, mock_stomp_message, mock_message, prefix, mocker):
    callback = mocker.MagicMock()

    pigeon_client._topic_prefix = prefix
    pigeon_client.subscribe("test.msg", callback)

    mock_stomp_message.headers["destination"] = (
        prefix + mock_stomp_message.headers["destination"]
    )

    pigeon_client._handle_message(mock_stomp_message)

    callback.assert_called()


@pytest.mark.parametrize("prefix", ["p1/", "prefix2."])
def test_missing_prefix(
    pigeon_client, mock_stomp_message, mock_message, prefix, mocker
):
    callback = mocker.MagicMock()

    pigeon_client._topic_prefix = prefix
    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)

    callback.assert_not_called()


def test_one_arg(pigeon_client, mock_stomp_message, mock_message):
    def callback(msg):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()

    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_two_args(pigeon_client, mock_stomp_message, mock_message):
    def callback(msg, topic):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"

    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_three_args(pigeon_client, mock_stomp_message, mock_message):
    def callback(msg):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert msg == mock_message.deserialize()
        assert topic == "test.msg"
        assert headers == mock_stomp_message.headers

    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def test_var_args(pigeon_client, mock_stomp_message, mock_message):
    def callback(*args):
        mock_message.deserialize.assert_called_with(mock_stomp_message.body)
        assert len(args) == 3
        assert args[0] == mock_message.deserialize()
        assert args[1] == "test.msg"
        assert args[2] == mock_stomp_message.headers

    pigeon_client.subscribe("test.msg", callback)

    pigeon_client._handle_message(mock_stomp_message)


def create_mock_message(body="", **headers):
    return MagicMock(body=body, headers=headers)


def test_topic_does_not_exist(pigeon_client):
    mock_message = create_mock_message(destination="not.a.real.message")

    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "Received a message on an unregistered topic: not.a.real.message"
    )


def test_validation_error(pigeon_client):
    mock_message = create_mock_message(destination="test")
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
    mock_message = create_mock_message(destination="test")

    pigeon_client.register_topic("test", MagicMock())
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        "No callback for message received on topic 'test'."
    )


def test_bad_signature(pigeon_client):
    mock_message = create_mock_message(destination="test")
    callback = lambda a, b, c, d: None

    pigeon_client.register_topic("test", MagicMock())
    pigeon_client.subscribe("test", callback)
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback signature for topic 'test' not acceptable. Call failed with error:\nFunction '{callback}' requires 4 positional arguments, but only 3 are available."
    )


def test_callback_exception(pigeon_client):
    mock_message = create_mock_message(destination="test")

    pigeon_client.register_topic("test", MagicMock())
    pigeon_client.subscribe(
        "test",
        MagicMock(side_effect=RecursionError("This is a test error.")),
    )
    pigeon_client._handle_message(mock_message)

    pigeon_client._logger.warning.assert_called_with(
        f"Callback for topic 'test' failed with error:", exc_info=True
    )
