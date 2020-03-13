import json
import logging.handlers
import socket
from typing import Any, Dict, Optional, Tuple
import warnings


class GelfFormatter(logging.Formatter):

    version = '1.1'
    json_default = str

    def __init__(self, host=None):
        if host is None:
            host = socket.gethostname()
        self.host = host

    def get_level(self, record) -> int:
        for threshold, gelf_level in [
            (logging.CRITICAL, 2),
            (logging.ERROR,    3),
            (logging.WARNING,  4),
            (logging.INFO,     6),
        ]:
            if record.levelno >= threshold:
                return gelf_level
        return 7

    def get_exception(self, record) -> Optional[str]:
        # Code for exception is copy-pasted from `logging.Formatter` class
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        return record.exc_text

    def get_message(self, record) -> Tuple[str, Optional[str]]:
        """ Return `short_message, full_message` pair """
        message = record.getMessage().strip('\n')
        exception = self.get_exception(record)
        if exception:
            message = f'{message}\n\n{exception}'

        if '\n' in message:
            short_message = message.split('\n', 1)[0]
            return short_message, message
        else:
            return message, None

    def get_gelf_fields(self, record):
        # https://docs.graylog.org/en/3.2/pages/gelf.html#gelf-payload-specification
        short_message, full_message = self.get_message(record)
        fields = {
            'version': self.version,
            'host': self.host,
            'short_message': short_message,
            'timestamp': record.created,
            'level': self.get_level(record),
        }
        if full_message:
            fields['full_message'] = full_message
        return fields

    def get_extension_fields(self, record):
        return {}

    def to_json(self, fields: Dict[str, Any]):
        return json.dumps(
            fields, separators=(',', ':'), default=self.json_default,
        )

    def format(self, record):
        fields = self.get_gelf_fields(record)
        for name, value in self.get_extension_fields(record):
            if name == 'id':
                warnings.warn('"id" field is not allowed in GELF')
                continue
            fields[f'_{name}'] = value
        return self.to_json(fields)


class BaseGelfHandler(logging.Handler):

    def setFormatter(self, formatter):
        if not isinstance(formatter, GelfFormatter):
            raise TypeError(
                f"{type(self).__name__}'s formatter must be instance of "
                f"GelfFormatter or it's subclass"
            )
        super().setFormatter(formatter)

    def format(self, record):
        if self.formatter is None:
            self.formatter = GelfFormatter()
        return self.formatter.format(record)


class GelfTcpHandler(BaseGelfHandler, logging.handlers.SocketHandler):
    # https://docs.graylog.org/en/3.2/pages/gelf.html#gelf-via-tcp

    def makePickle(self, record):
        return self.format(record).encode('utf-8') + b'\0'
