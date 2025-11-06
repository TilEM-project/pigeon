import logging
import os
import socket
import time
from importlib.metadata import entry_points
from typing import Callable, Dict

import stomp
import stomp.exception
from pydantic import ValidationError
from stomp.utils import Frame

from . import messages
from . import exceptions
from .utils import call_with_correct_args, get_version
from threading import Thread


def get_str_time_ms():
    return str(int(time.time_ns() / 1e6))


class Pigeon:
    """A STOMP client with message definitions via Pydantic

    This class is a STOMP message client which will automatically serialize and
    deserialize message data using Pydantic models. Before sending or receiving
    messages, topics must be "registered", or in other words, have a Pydantic
    model associated with each STOMP topic that will be used. This can be done
    in two ways. One is to use the register_topic(), or register_topics()
    methods. The other is to have message definitions in a Python package
    with an entry point defined in the pigeon.msgs group. This entry point
    should provide a tuple containing a mapping of topics to Pydantic models.
    Topics defined in this manner will be automatically discovered and loaded at
    runtime, unless this mechanism is manually disabled.
    """

    def __init__(
        self,
        service: str,
        host: str = "127.0.0.1",
        port: int = 61616,
        logger: logging.Logger = None,
        load_topics: bool = True,
        spawn_threads: bool = False,
        connection_timeout: float = 10,
        send_timeout: float = 0,
    ):
        """
        Args:
            service: The name of the service. This will be included in the
                message headers.
            host: The location of the STOMP message broker.
            port: The port to use when connecting to the STOMP message broker.
            logger: A Python logger to use. If not provided, a logger will be
                crated.
            load_topics: If true, load topics from Python entry points.
            spawn_threads: If true, create a new thread for every message received.
            connection_timeout: The number of seconds to attempt to connect to the broker.
                Set to None to attempt to connect indefinitely.
            send_timeout: The number of seconds to attempt to send a message, or None to
                try indefinitely.

        """
        self._service = service
        self._spawn_threads = spawn_threads
        self._connection = stomp.Connection12([(host, port)], heartbeats=(10000, 10000))
        self._connected = False
        self._connection_timeout = connection_timeout
        self._send_timeout = send_timeout
        self._username = None
        self._password = None
        self._topics = {}
        self._topic_versions = {}
        if load_topics:
            self._load_topics()
        self._callbacks: Dict[str, Callable] = {}
        self._connection.set_listener(
            "listener", PigeonListener(self._handle_message, self._handle_reconnect)
        )
        self._logger = logger if logger is not None else logging.getLogger(__name__)

        self._pid = os.getpid()
        self._hostname = socket.gethostname().split(".")[0]
        self._name = f"{self._service}_{self._pid}_{self._hostname}"

    def _load_topics(self):
        for entrypoint in entry_points(group="pigeon.msgs"):
            self.register_topics(entrypoint.load())

    def register_topic(self, topic: str, msg_class: Callable):
        """Register message definition for a given topic.

        Args:
            topic: The topic that this message definition applies to.
            msg_class: The Pydantic model definition of the message.
        """
        self._topics[topic] = msg_class
        self._topic_versions[topic] = get_version(msg_class)

    def register_topics(self, topics: Dict[str, Callable]):
        """Register a number of message definitions for multiple topics.

        Args:
            topics: A mapping of topics to Pydantic model message definitions.
        """
        for topic in topics.items():
            self.register_topic(*topic)

    def connect(self, username: str = None, password: str = None):
        """
        Connects to the STOMP server using the provided username and password.

        Args:
            username (str, optional): The username to authenticate with. Defaults to None.
            password (str, optional): The password to authenticate with. Defaults to None.

        Raises:
            stomp.exception.ConnectFailedException: If the connection to the server fails.
        """
        self._username = username if username is not None else self._username
        self._password = password if password is not None else self._password

        start = time.time()
        while True:
            try:
                self._connection.connect(
                    username=self._username, passcode=self._password, wait=True
                )
                break
            except stomp.exception.ConnectFailedException as e:
                if (
                    self._connection_timeout is None
                    or time.time() - start < self._connection_timeout
                ):
                    self._logger.error(
                        f"Connection failed: {e}. Attempting to reconnect."
                    )
                    time.sleep(1)
                else:
                    raise stomp.exception.ConnectFailedException(
                        f"Could not connect to server: {e}"
                    ) from e

        self._logger.info("Connected to STOMP server.")

        self._connected = True

    def send(self, topic: str, timeout=..., **data):
        """
        Sends data to the specified topic.

        Args:
            topic (str): The topic to send the data to.
            timeout (float, None): The length of time to attempt to send the
                message, or None to try indefinitely. If set to ..., the default,
                the send_timeout value from the client constructor will be used.
            **data: Keyword arguments representing the data to be sent.

        Raises:
            exceptions.NoSuchTopicException: If the specified topic is not defined.
            TimeoutError: If the message was not able to be sent within the required
                timeframe.
        """
        self._send(topic, data, timeout=timeout)

    def _send(self, topic, data, timeout=..., headers={}):
        """
        Sends data to the specified topic.

        Args:
            topic (str): The topic to send the data to.
            data: The data to send.
            timeout (float, None): The length of time to attempt to send the
                message, or None to try indefinitely. If set to ..., the default,
                the send_timeout value from the client constructor will be used.
            headers: Extra headers to send along with the data.

        Raises:
            exceptions.NoSuchTopicException: If the specified topic is not defined.
            TimeoutError: If the message was not able to be sent within the required
                timeframe.
        """
        self._ensure_topic_exists(topic)
        message = self._topics[topic](**data)
        _headers = dict(
            source=self._name,
            service=self._service,
            hostname=self._hostname,
            pid=self._pid,
            sent_at=get_str_time_ms(),
            version=self._topic_versions[topic],
        )
        _headers.update(headers)
        _timeout = self._send_timeout if timeout is ... else timeout
        assert isinstance(_timeout, (int, float, type(None)))
        start = time.time()
        while True:
            error = None
            if self._connected:
                try:
                    self._connection.send(
                        destination=topic, body=message.serialize(), headers=_headers
                    )
                    self._logger.debug(f"Sent data to {topic}: {message}")
                    return
                except (OSError, stomp.exception.ConnectFailedException) as e:
                    error = e
            if _timeout is not None and time.time() - start >= _timeout:
                exception = TimeoutError(
                    f"Could not send message on topic {topic} within {_timeout} seconds."
                )
                if error is not None:
                    raise exception from error
                else:
                    raise exception
            time.sleep(0.2)

    def _ensure_topic_exists(self, topic: str):
        if topic not in self._topics or topic not in self._topic_versions:
            raise exceptions.NoSuchTopicException(f"Topic {topic} not defined.")

    def _handle_reconnect(self):
        self._connected = False
        self._logger.warning("Disconnected from broker. Attempting to reconnect...")
        old_subscriptions = dict(self._callbacks)
        self._callbacks = {}
        time.sleep(1)
        self.connect()
        for topic, callback in old_subscriptions.items():
            self.subscribe(topic, callback)

    def _handle_message(self, message_frame: Frame):
        topic = message_frame.headers["subscription"]
        if topic not in self._topics:
            self._logger.warning(
                f"Received a message on an unregistered topic: {topic}"
            )
            return
        try:
            message_data = self._topics[topic].deserialize(message_frame.body)
        except ValidationError as e:
            version = message_frame.headers.get("version", "[undefined]")
            self._logger.warning(
                f"Failed to deserialize message on topic '{topic}' due to error:\n{e}Installed message version is {self._topic_versions[topic]} and received message version is {version}"
            )
            return
        callback = self._callbacks.get(topic)
        if callback is None:
            self._logger.warning(
                f"No callback for message received on topic '{topic}'."
            )
            return
        if not self._spawn_threads:
            self._run_callback(callback, message_data, topic, message_frame.headers)
        else:
            Thread(
                target=self._run_callback,
                args=(callback, message_data, topic, message_frame.headers),
            ).start()

    def _run_callback(self, callback, message_data, topic, headers):
        try:
            call_with_correct_args(callback, message_data, topic, headers)
        except exceptions.SignatureException as e:
            self._logger.warning(
                f"Callback signature for topic '{topic}' not acceptable. Call failed with error:\n{e}"
            )
        except Exception as e:
            self._logger.warning(
                f"Callback for topic '{topic}' failed with error:", exc_info=True
            )

    def subscribe(self, topic: str, callback: Callable):
        """
        Subscribes to a topic and associates a callback function to handle incoming messages.

        Args:
            topic (str): The topic to subscribe to.
            callback (Callable): The callback function to handle incoming
                messages. It may accept up to three arguments. In order, the
                arguments are, the received message, the topic the message was
                received on, and the message headers.

        Raises:
            NoSuchTopicException: If the specified topic is not defined.
        """
        self._ensure_topic_exists(topic)
        if topic not in self._callbacks:
            self._connection.subscribe(destination=topic, id=topic)
        self._callbacks[topic] = callback
        self._logger.info(f"Subscribed to {topic} with {callback}.")

    def subscribe_all(self, callback: Callable):
        """Subscribes to all registered topics.

        Args:
            callback: The function to call when a message is received. It must
                accept two arguments, the topic and the message data.
            include_core (bool): If true, subscribe all will subscribe the client to core messages.
        """

        if len(self._topics) == 0:
            self._logger.warning("No topics registered!")
        for topic in self._topics:
            self.subscribe(topic, callback)

    def unsubscribe(self, topic: str):
        """Unsubscribes from a given topic.

        Args:
            topic: The topic to unsubscribe from."""
        self._ensure_topic_exists(topic)
        self._connection.unsubscribe(id=topic)
        self._logger.info(f"Unsubscribed from {topic}.")
        del self._callbacks[topic]

    def disconnect(self):
        """Disconnect from the STOMP message broker."""
        if self._connection.is_connected():
            self._connection.disconnect()
            self._logger.info("Disconnected from STOMP server.")


class PigeonListener(stomp.ConnectionListener):
    def __init__(self, message_handler: Callable, disconnect_handler: Callable):
        self.message_handler = message_handler
        self.disconnect_handler = disconnect_handler

    def on_message(self, frame):
        frame.headers["received_at"] = get_str_time_ms()
        self.message_handler(frame)

    def on_disconnected(self):
        self.disconnect_handler()
