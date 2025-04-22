from __future__ import annotations
import asyncio
import re
from traceback import print_exception
from typing import Any


_LINE = re.compile("[\r\n]")


async def redirect_output(
    label: str, stream: asyncio.StreamReader | None, *fds: Any
) -> None:
    if stream is None:
        return

    try:
        while True:
            buf = await stream.read(2**16)
            if buf == b"":
                break

            for line in buf.splitlines():
                strline = line.decode("utf-8", errors="replace")
                for fd in fds:
                    print(f"{label}> {strline}", file=fd)
    except Exception as exc:
        for fd in fds:
            print_exception(exc, file=fd)
