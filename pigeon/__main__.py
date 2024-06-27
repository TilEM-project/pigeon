from .client import Pigeon
import argparse
import yaml
from functools import partial


class Listener:
    def __init__(self, disp_headers):
        self.message_received = False
        self.disp_headers = disp_headers

    def callback(self, msg, topic, headers):
        print(f"Recieved message on topic '{topic}':")
        print(msg)
        if self.disp_headers:
            print("With headers:")
            for key, val in headers.items():
                print(f"{key}={val}")
        self.message_received = True


def main():
    parser = argparse.ArgumentParser(prog="Pigeon CLI")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="The message broker to connect to.",
    )
    parser.add_argument(
        "--port", type=int, default=61616, help="The port to use for the connection."
    )
    parser.add_argument(
        "--username",
        type=str,
        help="The username to use when connecting to the STOMP server.",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="The password to use when connecting to the STOMP server.",
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
        "--one", action="store_true", help="Exit after receiving one message."
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List registered topics and exit."
    )
    parser.add_argument(
        "--headers", action="store_true", help="Display headers of received messages."
    )

    args = parser.parse_args()

    if args.list:
        connection = Pigeon("CLI")
        for topic in connection._topics:
            print(topic)
        return

    if args.publish is None and args.subscribe is None and not args.all:
        print("No action specified.")
        return

    if args.publish and args.data is None:
        print("Must also specify data to publish.")
        return

    if args.data and args.publish is None:
        print("Most also specify topic to publish data to.")
        return

    connection = Pigeon("CLI", args.host, args.port)
    connection.connect(args.username, args.password)

    if args.publish:
        connection.send(args.publish, **yaml.safe_load(args.data))

    if args.subscribe or args.all:
        listener = Listener(args.headers)

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
    exit(0)


if __name__ == "__main__":
    main()
