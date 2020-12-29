from functools import partial
import gzip
import json
import logging.handlers
import os
import socket
from typing import (
    Any, Callable, Dict, Iterable, Optional, Mapping, Tuple, Union,
)
import warnings


COMPRESS_NONE = lambda data: data
COMPRESS_GZIP = partial(gzip.compress, compresslevel=3)

CHUNK_SIZE_MIN = 16  # > header (12 bytes)
CHUNK_SIZE_MAX = 65536
CHUNK_SIZE_DEFAULT = 8192  # Supported by all components


class InvalidField(Warning):
    pass

class MessageTooLarge(Warning):
    pass


_STD_RECORD_ATTRS = set(
    logging.LogRecord(None, None, "", 0, "", (), None, None).__dict__
)


class GelfFormatter(logging.Formatter):
    """ Format record in GELF format (JSON string) """

    version = '1.1'
    json_default = str

    def __init__(
        self, *,
        record_fields: Union[Iterable[str], Mapping[str, str]] = ('name',),
        fixed_fields: Mapping[str, Any] = {},
        include_extra_fields = False,
    ):
        """
        :param record_fields: either sequence of mapping of LogRecord
        additional field names or mapping of LogRecord field names to
        field names in Graylog.

        :param fixed_fields: mapping of additional field names to values for
        extra fields with fixed values.

        :param include_extra_fields: whether to include all extra record fields
        """
        self.host = self.get_host()
        if not isinstance(record_fields, Mapping):
            record_fields = {name: name for name in record_fields}
        else:
            record_fields = dict(record_fields)
        self.record_fields = record_fields
        self.fixed_fields = dict(fixed_fields)
        self.include_extra_fields = include_extra_fields

    @staticmethod
    def get_host():
        return socket.gethostname()

    @staticmethod
    def get_level(record) -> int:
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

    def get_additional_fields(self, record):
        fields = dict(self.fixed_fields)

        all_attr_names = set(record.__dict__)
        record_attr_names = set(self.record_fields) & all_attr_names
        if self.include_extra_fields:
            record_attr_names |= all_attr_names - _STD_RECORD_ATTRS

        for attr_name in record_attr_names:
            graylog_name = self.record_fields.get(attr_name, attr_name)
            fields[graylog_name] = getattr(record, attr_name)

        return fields

    def to_json(self, fields: Dict[str, Any]):
        return json.dumps(
            fields, separators=(',', ':'), default=self.json_default,
        )

    def format(self, record):
        fields = self.get_gelf_fields(record)
        for name, value in self.get_additional_fields(record).items():
            if name == 'id':
                warnings.warn(
                    '"id" field is not allowed in GELF', category=InvalidField,
                )
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


_CHUNKED_MAGIC = b'\x1e\x0f'
_CHUNKED_HEADER_SIZE = 12  # 2 magic, 8 message_id, 1 index, 1 count
_CHUNKS_COUNT_MAX = 128


class GelfUdpHandler(BaseGelfHandler, logging.handlers.DatagramHandler):
    # https://docs.graylog.org/en/3.2/pages/gelf.html#gelf-via-udp

    def __init__(
        self, host, port,
        compress: Optional[Callable[[bytes], bytes]] = COMPRESS_GZIP,
        chunk_size: int = CHUNK_SIZE_DEFAULT,
    ):
        super().__init__(host, port)
        if compress is None:
            compress = COMPRESS_NONE
        self.compress = compress
        if not CHUNK_SIZE_MIN <= chunk_size <= CHUNK_SIZE_MAX:
            raise ValueError('Invalid chunk_size')
        self.chunk_size = chunk_size

    def makePickle(self, record):
        return self.compress(self.format(record).encode('utf-8'))

    def send(self, data: bytes):
        for chunk in chunked(data, self.chunk_size):
            logging.handlers.DatagramHandler.send(self, chunk)


def chunked(data: bytes, chunk_size: int):
    length = len(data)
    if length > chunk_size:
        chunk_data_size = chunk_size - _CHUNKED_HEADER_SIZE
        max_size = chunk_data_size * _CHUNKS_COUNT_MAX
        if length > max_size:
            warnings.warn(
                f'Message is too large ({length} > {max_size}). '
                    f'Try increasing chunk_size parameter',
                category=MessageTooLarge,
            )
            return

        message_id = os.urandom(8)
        starts = range(0, length, chunk_data_size)
        chunks_count = len(starts)
        for index, start in enumerate(starts):
            yield b''.join([
                _CHUNKED_MAGIC,
                message_id,
                bytes([index, chunks_count]),
                data[start:start+chunk_data_size],
            ])
    else:
        yield data
