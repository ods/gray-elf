gray-elf
========

Python logging formatter and handlers for Graylog Extended Log Format (GELF)


Simple usage
------------

.. code-block:: python

    import logging
    from gray_elf import GelfUdpHandler

    logging.root.addHandler(
        GelfUdpHandler(host=GRAYLOG_HOST, port=GRAYLOG_PORT)
    )


Customizing data serialization
------------------------------

The example below adds the following features to formatter:

* serializes big integers as strings to avoid rounding;
* uses more readable representations for protobuf messages;
* sends extra fields of log record.

.. code-block:: python

    import logging
    from gray_elf import GelfFormatter, GelfUdpHandler
    from google.protobuf.message import Message
    from google.protobuf.text_format import MessageToString
    import simplejson


    class CustomGelfFormatter(GelfFormatter):

        @staticmethod
        def json_default(value):
            if not isinstance(value, Message):
                return str(value)

            text = MessageToString(message, indent=2)

            if not text:
                return f'{message.DESCRIPTOR.full_name}()'

            lines = [f'{message.DESCRIPTOR.full_name}(']
            for line in text.splitlines():
                if len(line) > 79:
                    line = f'{line[:75]}...{line[-1:]}'
                lines.append(line)
            lines.append(')')
            return '\n'.join(lines)

        def to_json(self, fields):
            return simplejson.dumps(
                fields, separators=(',', ':'), default=self.json_default,
                bigint_as_string=True, allow_nan=False,
            )


    handler = GelfUdpHandler(host=GRAYLOG_HOST, port=GRAYLOG_PORT)
    handler.setFormatter(CustomGelfFormatter(include_extra_fields=True))
    logging.root.addHandler(handler)


Change log
----------

See `CHANGELOG <https://github.com/ods/gray-elf/blob/master/CHANGELOG.rst>`_.
