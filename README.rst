gray-elf
========

Python logging formatter and handlers for Graylog Extended Log Format (GELF)


Simple usage
------------

.. code-block:: python

    import logging
    from gray_elf import GelfTcpHandler

    logging.root.addHandler(
        GelfTcpHandler(host=GRAYLOG_HOST, port=GRAYLOG_PORT)
    )


Change log
----------

See `CHANGELOG <https://github.com/ods/gray-elf/blob/master/CHANGELOG.rst>`_.
