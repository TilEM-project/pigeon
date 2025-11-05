from .client import Pigeon
import argparse
import yaml
import json
from os import environ
import jsonschema2md
from rich.console import Console
from rich.markdown import Markdown
import re
from datetime import datetime
from pydantic import BaseModel
from time import time, sleep


jsonschema2md.Parser.current_locale = "en_US"

console = Console()


class Listener:
    def __init__(self, disp_headers, record=None, rate=False, delay=False, quiet=False):
        self.message_received = False
        self.disp_headers = disp_headers
        self.record = record
        self.rate = rate
        self.delay = delay
        self.quiet = quiet
        self.messages = []
        self.last_timestamp = None

    @classmethod
    def _format(cls, data):
        markdown = []
        if isinstance(data, BaseModel):
            data = data.__dict__
        if isinstance(data, dict):
            for key, val in data.items():
                markdown.append(f"* **{key}**:")
                markdown += ["  " + m for m in cls._format(val)]
        elif isinstance(data, (list, tuple)):
            for val in data:
                child = cls._format(val)
                markdown.append(f"* {child[0]}")
                markdown += ["  " + m for m in child[1:]]
        else:
            markdown.append(str(data))
        return markdown

    @classmethod
    def _to_dict(cls, data):
        if isinstance(data, BaseModel):
            data = data.__dict__
        if isinstance(data, dict):
            return {key: cls._to_dict(val) for key, val in data.items()}
        if isinstance(data, (list, tuple)):
            return [cls._to_dict(val) for val in data]
        if isinstance(data, datetime):
            return data.isoformat()
        return data

    def callback(self, msg, topic, headers):
        if self.record is not None:
            self.messages.append(
                {
                    "msg": self._to_dict(msg),
                    "topic": topic,
                    "headers": headers,
                }
            )
        if not self.quiet:
            markdown = [f"# {topic}"]
            markdown += self._format(msg)
            if self.disp_headers:
                markdown.append(f"### Headers")
                markdown += [f"* **{key}**: {val}" for key, val in headers.items()]
            console.print(Markdown("\n".join(markdown)))
        if self.rate:
            if self.last_timestamp is not None:
                try:
                    rate = 1000 / (
                        int(headers.get("sent_at")) - int(self.last_timestamp)
                    )
                    print(f"Rate: {rate} Hz")
                except ValueError as e:
                    console.print("Could not parse timestamp:", style="red")
                    console.print(e, style="red")
            self.last_timestamp = headers.get("sent_at")
        if self.delay:
            delay = int(headers["received_at"]) - int(headers["sent_at"])
            console.print(f"{delay} ms")
        self.message_received = True

    def write(self):
        with open(self.record, "w") as f:
            json.dump(self.messages, f)


def main():
    parser = argparse.ArgumentParser(prog="Pigeon CLI")
    parser.add_argument(
        "--host",
        type=str,
        help="The message broker to connect to. Defaults to the PIGEON_HOST environment variable if set, otherwise 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="The port to use for the connection. Defaults to the PIGEON_PORT environment variable if set, otherwise 61616.",
    )
    parser.add_argument(
        "--username",
        type=str,
        help="The username to use when connecting to the STOMP server. The environment variable PIGEON_USERNAME is used if set.",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="The password to use when connecting to the STOMP server. The environment variable PIGEON_PASSWORD is used if set.",
    )
    subparsers = parser.add_subparsers(dest="command")

    publish = subparsers.add_parser(
        "publish", aliases=["p", "pub", "send"], help="Publish a message."
    )
    publish.add_argument("topic", type=str, help="The topic to publish a message to.")
    publish.add_argument(
        "data", type=str, help="The YAML/JSON formatted data to publish."
    )

    subscribe = subparsers.add_parser(
        "subscribe", aliases=["s", "sub"], help="Subscribe to topics."
    )
    subscribe.add_argument(
        "topic", type=str, nargs="*", help="The topic to subscribe to."
    )
    subscribe.add_argument(
        "-a", "--all", action="store_true", help="Subscribe to all registered topics."
    )
    subscribe.add_argument(
        "-1", "--one", action="store_true", help="Exit after receiving one message."
    )
    subscribe.add_argument(
        "--headers", action="store_true", help="Display headers of received messages."
    )

    list = subparsers.add_parser("list", aliases=["l"], help="List topics.")

    show = subparsers.add_parser(
        "show", aliases=["doc", "documentation"], help="Display message documentation."
    )
    show.add_argument(
        "topic", type=str, nargs="*", help="The topic to display the documentation for."
    )

    record = subparsers.add_parser("record", aliases=["r"], help="Record messages.")
    record.add_argument(
        "-o", "--output", type=str, help="The file to write the messages to."
    )
    record.add_argument(
        "-a", "--all", action="store_true", help="Subscribe to all registered topics."
    )
    record.add_argument("topic", type=str, nargs="*", help="The topic to record.")

    play = subparsers.add_parser("play", help="Playback recorded messages.")
    play.add_argument(
        "-i",
        "--immediate",
        action="store_true",
        help="Publish all messages without waiting.",
    )
    play.add_argument(
        "-r",
        "--rate",
        type=float,
        default=1,
        help="Multiple the publish rate by this factor.",
    )
    play.add_argument("file", type=str, help="The file to playback.")

    rate = subparsers.add_parser(
        "rate", aliases=["hz"], help="Display the rate at which messages are received."
    )
    rate.add_argument("topic", type=str, help="The topic to use for rate calculations.")

    delay = subparsers.add_parser(
        "delay", aliases=["d"], help="Display the latency of each received message."
    )
    delay.add_argument("topic", type=str, help="The topic to measure the latency of.")

    args = parser.parse_args()

    if args.command is None:
        console.print("No subcommand specified!", style="red")
        exit(1)

    connection = Pigeon(
        "CLI",
        environ.get("PIGEON_HOST", "127.0.0.1") if args.host is None else args.host,
        environ.get("PIGEON_PORT", 61616) if args.port is None else args.port,
    )

    match args.command:
        case "list" | "l":
            markdown = ["# Topics"]
            markdown += [f"* {topic}" for topic in connection._topics]
            console.print(Markdown("\n".join(markdown)))
            exit(0)
        case "show" | "doc" | "documentation":
            parser = jsonschema2md.Parser()
            for topic in args.topic:
                if topic not in connection._topics:
                    print(f"Topic {topic} not found!")
                    continue
                schema = connection._topics[topic].model_json_schema()
                schema["title"] = topic
                markdown = "".join(parser.parse_schema(schema))
                markdown = re.sub(r"<a.*?>(.*?)</a>", r"\1", markdown)
                console.print(Markdown(markdown))
            exit(0)

    connection.connect(
        environ.get("PIGEON_USERNAME") if args.username is None else args.username,
        environ.get("PIGEON_PASSWORD") if args.password is None else args.password,
    )

    match args.command:
        case "publish" | "p" | "pub" | "send":
            connection.send(args.topic, **yaml.safe_load(args.data))
            exit(0)
        case "play":
            with open(args.file) as f:
                messages = json.load(f)
            message_start_time = int(messages[0]["headers"]["sent_at"]) / 1000
            playback_start_time = time()
            for message in messages:
                if not args.immediate:
                    playback_time = args.rate * (time() - playback_start_time)
                    message_time = (
                        int(message["headers"]["sent_at"]) / 1000
                    ) - message_start_time
                    if playback_time < message_time:
                        sleep((message_time - playback_time) / args.rate)
                connection.send(message["topic"], **message["msg"])
            exit(0)
        case "subscribe" | "s" | "sub":
            listener = Listener(args.headers)
            for topic in args.topic:
                connection.subscribe(topic, listener.callback)
            if args.all:
                connection.subscribe_all(listener.callback)
        case "rate" | "hz":
            listener = Listener(False, rate=True, quiet=True)
            connection.subscribe(args.topic, listener.callback)
        case "record" | "r":
            output = args.output
            if output is None:
                output = datetime.now().isoformat()
            if not output.lower().endswith(".json"):
                output += ".json"
            listener = Listener(False, record=output, quiet=True)
            for topic in args.topic:
                connection.subscribe(topic, listener.callback)
            if args.all:
                connection.subscribe_all(listener.callback)
        case "delay" | "d":
            listener = Listener(False, delay=True, quiet=True)
            connection.subscribe(args.topic, listener.callback)

    if len(connection._callbacks) <= 1:
        console.print("No subscriptions, exiting...", style="red")
        exit(0)

    try:
        while not (getattr(args, "one", False) and listener.message_received):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        if listener.record is not None:
            console.print(
                f"Writing {len(listener.messages)} messages to `{listener.record}`",
                style="grey50",
            )
            listener.write()
        console.print("exiting...", style="grey50")

    exit(0)


if __name__ == "__main__":
    main()
