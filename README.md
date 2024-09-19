[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/AllenInstitute/pigeon/test.yaml)](https://github.com/AllenInstitute/pigeon/actions)
[![Documentation Status](https://readthedocs.org/projects/pigeon/badge/?version=latest)](https://pigeon.readthedocs.io/en/latest/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/pigeon-client)](https://pypi.org/project/pigeon-client/)

# Pigeon

Pigeon is a combination of a [STOMP client](https://pypi.org/project/stomp-py/), and a message definition system using [Pydantic](https://docs.pydantic.dev/latest/) models.

## Message Definitions

Messages are defined by writing a Pydantic model for each topic. These messages can be registered at runtime, or placed in a Python package and automatically loaded when Pigeon is imported using an [entrypoint](https://packaging.python.org/en/latest/specifications/entry-points/).

## Logging

When a Pigeon client is instantiated, a logger is created. If desired, logs can also be sent to [Grafana Loki](https://grafana.com/oss/loki/) by setting environment variables.

| Variable      | Documentation                                                                 |
| ------------- | ----------------------------------------------------------------------------- |
| LOKI_URL      | The URL of the location of the Loki Server                                    |
| LOKI_TAGS     | A mapping using colons to split tags and values, and commas to separate pairs |
| LOKI_USERNAME | The username to use when connecting to the server                             |
| LOKI_PASSWORD | The password to use when connecting to the server                             |
| LOKI_VERSION  | The version of the Loki Emitter to use                                        |

## Templates

To ease the creation of services using Pigeon, a [Cookiecutter](https://cookiecutter.readthedocs.io/en/stable/) [template](https://github.com/AllenInstitute/pigeon-service-cookiecutter) is available. Similarly, a [template](https://github.com/AllenInstitute/pigeon-msgs-cookiecutter) for a message definition package is available.
