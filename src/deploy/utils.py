from __future__ import annotations
import asyncio
from typing import Any


async def redirect_output(
    label: str, stream: asyncio.StreamReader | None, *fds: Any
) -> None:
    if stream is None:
        return

    async for line in stream:
        for fd in fds:
            print(f"{label}> {line.decode('utf-8', errors='replace')[:-1]}", file=fd)
