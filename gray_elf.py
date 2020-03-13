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
        """ Return Graylog level (= standard syslog level) """
        for threshold, gelf_level in [
            (logging.CRITICAL, 2),
            (logging.ERROR,    3),
            (logging.WARNING,  4),
            (logging.INFO,     6),
        ]:
            if record.levelno >= threshold:
                return gelf_level
        return 7

    def get_message(self, record) -> Tuple[str, Optional[str]]:
        """ Return `short_message, full_message` pair """
        message = record.getMessage().rstrip('\n')

        # Caching like in `logging.Formatter` class
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            message = f'{message}\n\n{record.exc_text}'.rstrip('\n')

        if record.stack_info:
            message = f'{message}\n\n{self.formatStack(record.stack_info)}'

        return message

    def get_message_fields(self, record):
        message = self.get_message(record)
        if '\n' in message:
            return {
                'short_message': message.split('\n', 1)[0],
                'full_message': message,
            }
        else:
            return {'short_message': message}

    def get_gelf_fields(self, record):
        # https://docs.graylog.org/en/3.2/pages/gelf.html#gelf-payload-specification
        return {
            'version': self.version,
            'host': self.host,
            'timestamp': record.created,
            'level': self.get_level(record),
            **self.get_message_fields(record),
        }

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
