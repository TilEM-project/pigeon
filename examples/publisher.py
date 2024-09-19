import os
import time

from pigeon.client import Pigeon
from pigeon.utils import setup_logging
from pigeon import BaseMessage


class TestMsg(BaseMessage):
    data: str


logger = setup_logging("publisher")

host = os.environ.get("ARTEMIS_HOST", "127.0.0.1")
port = int(os.environ.get("ARTEMIS_PORT", 61616))

connection = Pigeon("Publisher", host=host, port=port, logger=logger, load_topics=False)
connection.register_topic("test", TestMsg)
connection.connect(username="admin", password="password")

while True:
    connection.send("test", data="test_data")
    time.sleep(1)
