import os

from pigeon.client import Pigeon
from pigeon.utils import setup_logging
from pigeon import BaseMessage

logger = setup_logging("subscriber")

host = os.environ.get("ARTEMIS_HOST", "127.0.0.1")
port = int(os.environ.get("ARTEMIS_PORT", 61616))


class TestMsg(BaseMessage):
    data: str


def handle_test_message(topic, message):
    logger.info(f"Received {topic} message: {message}")


connection = Pigeon(
    "Subscriber",
    host=host,
    port=port,
    logger=logger,
    load_topics=False,
    connection_timeout=None,
)
connection.register_topic("test", TestMsg)
connection.connect(username="admin", password="password")
connection.subscribe("test", handle_test_message)

while True:
    pass
