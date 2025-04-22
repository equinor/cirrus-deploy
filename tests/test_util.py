from typing import AsyncIterator
from deploy import utils

import sys
import asyncio
import pytest
from contextlib import asynccontextmanager


@asynccontextmanager
async def make_stream() -> AsyncIterator[asyncio.StreamReader]:
    stream = asyncio.StreamReader()
    task = asyncio.create_task(utils.redirect_output("label", stream, sys.stdout))

    try:
        yield stream
        await asyncio.wait_for(task, timeout=5)
    finally:
        task.cancel()


@pytest.fixture
async def stream() -> AsyncIterator[asyncio.StreamReader]:
    stream = asyncio.StreamReader()
    task = asyncio.create_task(utils.redirect_output("label", stream, sys.stdout))

    try:
        yield stream
        await asyncio.wait_for(task, timeout=5)
    finally:
        task.cancel()


async def test_empty_stream(
    stream: asyncio.StreamReader, capsys: pytest.CaptureFixture
):
    stream.feed_eof()

    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


async def test_complete_stream(capsys: pytest.CaptureFixture):
    async with make_stream() as stream:
        stream.feed_data(b"Hello, world!\n")
        stream.feed_data(b"Goodbye, world!\n")
        stream.feed_eof()

    out, err = capsys.readouterr()
    assert out == "label> Hello, world!\nlabel> Goodbye, world!\n"
    assert err == ""


async def test_complete_with_delay(capsys: pytest.CaptureFixture):
    async with make_stream() as stream:
        stream.feed_data(b"Hello, world!\n")
        await asyncio.sleep(0)
        assert capsys.readouterr() == ("label> Hello, world!\n", "")

        stream.feed_data(b"Goodbye, world!\n")
        await asyncio.sleep(0)
        assert capsys.readouterr() == ("label> Goodbye, world!\n", "")

        stream.feed_eof()

    # Nothing left to read
    assert capsys.readouterr() == ("", "")


async def test_complete_with_partial(capsys: pytest.CaptureFixture):
    async with make_stream() as stream:
        stream.feed_data(b"Input your SSH password: ")
        await asyncio.sleep(0)
        assert capsys.readouterr() == ("label> Input your SSH password: \n", "")

        stream.feed_eof()

    # Nothing left to read
    assert capsys.readouterr() == ("", "")


async def test_carriage_return(capsys: pytest.CaptureFixture):
    async with make_stream() as stream:
        stream.feed_data(b"[1/2]\r[2/2]\n")
        await asyncio.sleep(0)
        assert capsys.readouterr() == ("label> [1/2]\nlabel> [2/2]\n", "")

        stream.feed_eof()

    # Nothing left to read
    assert capsys.readouterr() == ("", "")
