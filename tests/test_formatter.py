import json
import logging
import socket
from time import time

import pytest

from gray_elf import GelfFormatter, InvalidField


DEFAULT_MESSAGE = 'Message with 2 placeholders'


def get_record(
    name='test', level=logging.DEBUG, pathname='path/to/test.ext', lineno=42,
    msg='Message with %d %s', args=(2, 'placeholders'), exc_info=None,
    func=None, sinfo=None,
):
    return logging.LogRecord(**locals())


@pytest.mark.parametrize('py_level,graylog_level', [
    (1, 7), (10, 7), (19, 7),
    (20, 6), (29, 6),
    (30, 4), (39, 4),
    (40, 3), (49, 3),
    (50, 2), (100, 2),
])
def test_get_level(py_level, graylog_level):
    record = get_record(level=py_level)
    assert GelfFormatter.get_level(record) == graylog_level


def test_default(host):
    formatter = GelfFormatter()
    record = get_record()
    data = json.loads(formatter.format(record))
    assert data == {
        'version': '1.1',
        'host': host,
        'short_message': DEFAULT_MESSAGE,
        'timestamp': record.created,
        'level': 7,
        '_name': 'test',
    }


def test_record_fields_mapping(host):
    formatter = GelfFormatter(record_fields={
        'name': 'name',
        'levelname': 'levelname',
        'pathname': 'pathname',
        'lineno': 'line',
        'funcName': 'func',
        'thread': 'thread_id',
        'threadName': 'thread_name',
        'process': 'pid',
        'processName': 'process_name',
        'non_existent': 'missing',
    })
    record = get_record(func='test_func')
    data = json.loads(formatter.format(record))
    assert data == {
        'version': '1.1',
        'host': host,
        'short_message': DEFAULT_MESSAGE,
        'timestamp': record.created,
        'level': 7,
        '_name': 'test',
        '_levelname': 'DEBUG',
        '_pathname': record.pathname,
        '_line': record.lineno,
        '_func': 'test_func',
        '_thread_id': record.thread,
        '_thread_name': record.threadName,
        '_pid': record.process,
        '_process_name': record.processName,
    }


def test_multiline_message():
    formatter = GelfFormatter(record_fields=())
    record = get_record(msg='line1\nline2', args=())
    data = json.loads(formatter.format(record))
    assert data['short_message'] == 'line1'
    assert data['full_message'] == 'line1\nline2'


def test_exception():
    formatter = GelfFormatter(record_fields=())
    try:
        1 / 0
    except ZeroDivisionError as exc:
        record = get_record(exc_info=(exc.__class__, exc, exc.__traceback__))
    data = json.loads(formatter.format(record))
    assert data['short_message'] == DEFAULT_MESSAGE
    assert data['full_message'].startswith(DEFAULT_MESSAGE + '\n\nTraceback')
    assert data['full_message'].endswith('ZeroDivisionError: division by zero')


def test_stack_info():
    formatter = GelfFormatter(record_fields=())
    record = get_record(sinfo='Stack (most recent call last):\n...')
    data = json.loads(formatter.format(record))
    assert data['short_message'] == DEFAULT_MESSAGE
    assert data['full_message'] == DEFAULT_MESSAGE + '\n\n' + record.stack_info


def test_extra_fields(host):
    formatter = GelfFormatter(
        record_fields={'extra_mapped': 'mapped_to'},
        include_extra_fields=True,
    )
    record = get_record()
    record.extra_mapped = 123
    record.extra_asis = 'qwerty'
    data = json.loads(formatter.format(record))
    assert data == {
        'version': '1.1',
        'host': host,
        'short_message': DEFAULT_MESSAGE,
        'timestamp': record.created,
        'level': 7,
        '_mapped_to': 123,
        '_extra_asis': 'qwerty',
    }


@pytest.mark.parametrize('include_extra_fields', [False, True])
def test_id_field(host, include_extra_fields):
    formatter = GelfFormatter(
        record_fields={'source_field': 'id'},
        include_extra_fields=include_extra_fields,
    )
    record = get_record()
    record.source_field = 123
    with pytest.warns(InvalidField):
        formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data == {
        'version': '1.1',
        'host': host,
        'short_message': DEFAULT_MESSAGE,
        'timestamp': record.created,
        'level': 7,
    }
