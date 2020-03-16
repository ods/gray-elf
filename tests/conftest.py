from unittest import mock
import socket

import pytest


HOST = 'gray-elf.github.com'


@pytest.fixture(scope='session')
def host():
    with mock.patch.object(socket, 'gethostname', lambda: HOST):
        yield HOST
