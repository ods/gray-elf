import socket
from typing import Generator
from unittest import mock

import pytest


HOST = 'gray-elf.github.com'


@pytest.fixture(scope='session')
def host() -> Generator[str, None, None]:
    with mock.patch.object(socket, 'gethostname', lambda: HOST):
        yield HOST
