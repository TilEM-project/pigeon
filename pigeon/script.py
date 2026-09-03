import time

from .client import Pigeon
from .utils import call_with_correct_args


class NotReceived(Exception):
    pass


class PigeonScript(Pigeon):
    def __init__(self, *args, **kwargs):
        self._script_callbacks = {}
        self._messages = {}
        super().__init__(*args, **kwargs)

    def subscribe_all(self, callback=None):
        super().subscribe_all(callback)

    def subscribe(self, topic, callback=None):
        super().subscribe(topic, self._callback)
        if callback:
            if topic not in self._script_callbacks:
                self._script_callbacks[topic] = []
            self._script_callbacks[topic].append(callback)

    def remove_callback(self, topic, callback):
        assert topic in self._script_callbacks
        self._script_callbacks[topic].remove(callback)

    def _callback(self, msg, topic, headers):
        self._messages[topic] = msg
        for callback in list(self._script_callbacks.get(topic, [])):
            call_with_correct_args(callback, msg, topic, headers)

    def get_message(self, topic):
        if topic not in self._messages:
            raise NotReceived(f"No message on topic {topic} has been received")
        return self._messages[topic]

    def wait_for_message(self, topic, timeout=2, filter=None):
        message = None

        def callback(msg):
            nonlocal message
            if not filter or filter(msg):
                self.remove_callback(topic, callback)
                message = msg

        self.subscribe(topic, callback)

        start = time.time()
        while message is None and time.time() - start <= timeout:
            time.sleep(0.1)

        if message is None:
            self.remove_callback(topic, callback)
            raise TimeoutError(
                f"Did not receive an acceptable message on topic {topic} within {timeout} seconds"
            )

        return message
