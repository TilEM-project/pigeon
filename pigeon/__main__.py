from .client import Pigeon
import argparse
import yaml
from functools import partial
import json
from inspect import getsource
from textwrap import indent
from os import environ


class Listener:
    def __init__(self, disp_headers, record=False, rate=False, quiet=False):
        self.message_received = False
        self.disp_headers = disp_headers
        self.record = record
        self.rate = rate
        self.quiet = quiet
        self.messages = []
        self.last_timestamp = None

    def callback(self, msg, topic, headers):
        if self.record:
            self.messages.append(
                {
                    "msg": msg.__dict__,
                    "topic": topic,
                    "headers": headers,
                }
            )
        if not self.quiet:
            print(f"Recieved message on topic '{topic}':")
            print(msg)
            if self.disp_headers:
                print("With headers:")
                for key, val in headers.items():
                    print(f"{key}={val}")
        if self.rate:
            if self.last_timestamp is not None:
                try:
                    rate = 1000 / (
                        int(headers.get("sent_at")) - int(self.last_timestamp)
                    )
                    print(f"Rate: {rate} Hz")
                except ValueError as e:
                    print("Could not parse timestamp:")
                    print(e)
            self.last_timestamp = headers.get("sent_at")
        self.message_received = True

    def write(self, path):
        with open(path, "w") as f:
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
    parser.add_argument(
        "-p", "--publish", type=str, help="The topic to publish a message to."
    )
    parser.add_argument(
        "-d", "--data", type=str, help="The YAML/JSON formatted data to publish."
    )
    parser.add_argument(
        "-s",
        "--subscribe",
        type=str,
        action="append",
        default=[],
        help="The topic to subscribe to.",
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="Subscribe to all registered topics."
    )
    parser.add_argument(
        "-r", "--record", type=str, help="Write received messages to a JSON file."
    )
    parser.add_argument(
        "--rate",
        action="store_true",
        help="Display the rate at which messages are received.",
    )
    parser.add_argument(
        "-1", "--one", action="store_true", help="Exit after receiving one message."
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List registered topics and exit."
    )
    parser.add_argument(
        "--show",
        action="append",
        default=[],
        type=str,
        help="Show the message definition of the specified topic.",
    )
    parser.add_argument(
        "--headers", action="store_true", help="Display headers of received messages."
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Don't display incoming messages."
    )

    args = parser.parse_args()

    connection = Pigeon(
        "CLI",
        environ.get("PIGEON_HOST", "127.0.0.1") if args.host is None else args.host,
        environ.get("PIGEON_PORT", 61616) if args.port is None else args.port,
    )

    if args.list:
        for topic in connection._topics:
            print(topic)

    for topic in args.show:
        if topic not in connection._topics:
            print(f"Topic {topic} not defined!")
            continue
        print(f"{topic}:")
        print(indent(getsource(connection._topics[topic]), "    "))

    if args.publish is None and args.subscribe is None and not args.all:
        print("No action specified.")
        exit(1)

    if args.publish and args.data is None:
        print("Must also specify data to publish.")
        exit(1)

    if args.data and args.publish is None:
        print("Must also specify topic to publish data to.")
        exit(1)

    if args.record is not None and not (args.subscribe or args.all):
        print("No subscriptions to record.")
        exit(1)

    if args.publish or args.subscribe or args.all:
        connection.connect(
            environ.get("PIGEON_USERNAME") if args.username is None else args.username,
            environ.get("PIGEON_PASSWORD") if args.password is None else args.password,
        )

    if args.publish:
        connection.send(args.publish, **yaml.safe_load(args.data))

    if args.subscribe or args.all:
        listener = Listener(
            args.headers,
            record=args.record is not None,
            rate=args.rate,
            quiet=args.quiet,
        )

    if args.all:
        connection.subscribe_all(listener.callback)
    else:
        for topic in args.subscribe:
            connection.subscribe(topic, listener.callback)

    if args.subscribe or args.all:
        try:
            while not (args.one and listener.message_received):
                pass
        except KeyboardInterrupt:
            print("exiting")
        finally:
            if args.record is not None:
                listener.write(args.record)
    exit(0)


if __name__ == "__main__":
    main()
