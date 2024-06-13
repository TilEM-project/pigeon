Welcome to Pigeon's documentation!
==================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Pigeon is a combination of a `STOMP client <https://pypi.org/project/stomp-py/>`_, and a message definition system using `Pydantic <https://docs.pydantic.dev/latest/>`_ models. The message definitions can either be defined manually, or Pigeon can search for message definitions via Python entry-points. A template for message definitions is available `here <https://github.com/AllenInstitute/pigeon-msgs-cookiecutter>`_. Similarly, there is a template `here <https://github.com/AllenInstitute/pigeon-service-cookiecutter>`_ for creating a Dockerized service using Pigeon.

.. autoclass:: pigeon.Pigeon
   :members:

.. autoclass:: pigeon.BaseMessage

.. autoexception:: pigeon.exceptions.NoSuchTopicException
.. autoexception:: pigeon.exceptions.VersionMismatchException

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
