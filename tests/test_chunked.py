import itertools

import pytest

from gray_elf import chunked, MessageTooLarge


@pytest.mark.parametrize('message', [
    b'',
    b'0123456789abcdef',
])
def test_fits_in_one(message: bytes) -> None:
    chunks = list(chunked(message, 16))
    assert chunks == [message]


@pytest.mark.parametrize('message, tails', [
    (b'0123456789abcdef0', [
        b'\x00\x050123', b'\x01\x054567', b'\x02\x0589ab', b'\x03\x05cdef',
        b'\x04\x050',
    ]),
    (b'0123456789abcdef0123', [
        b'\x00\x050123', b'\x01\x054567', b'\x02\x0589ab', b'\x03\x05cdef',
        b'\x04\x050123',
    ]),
])
def test_normal(message: bytes, tails: bytes) -> None:
    chunks = list(chunked(message, 16))
    assert all(chunk.startswith(b'\x1e\x0f') for chunk in chunks)
    message_ids = set(chunk[2:10] for chunk in chunks)
    assert len(message_ids) == 1  # All are the same
    assert len(chunks) == len(tails)
    for chunk, tail in itertools.zip_longest(chunks, tails):
        assert chunk[10:] == tail


def test_max_count() -> None:
    chunks = list(chunked(b'0123' * 128, 16))
    assert len(chunks) == 128

    with pytest.warns(MessageTooLarge):
        chunks = list(chunked(b'0123' * 128 + b'0', 16))
    assert len(chunks) == 0
