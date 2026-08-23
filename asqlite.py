"""
Minimal stdlib-only async SQLite wrapper - replaces the `aiosqlite` pip
dependency.

Why this exists: on Termux, pre-built PyPI wheels are compiled for glibc
Linux and are incompatible with Android's Bionic libc, so pip falls back
to building packages from source - which needs a C compiler and often
fails or hangs. `sqlite3` ships built into every standard CPython install
(including Termux's `python` package), so wrapping it ourselves removes
one more thing that can fail to `pip install`.

Design: a single dedicated background thread owns the sqlite3.Connection
and processes all operations sequentially from a queue. This matches
aiosqlite's own architecture and sidesteps sqlite3's rule that a
connection may only safely be driven from one thread at a time - even
with check_same_thread=False, concurrent access from multiple threads is
not safe, only sequential access is.
"""

import asyncio
import queue
import sqlite3
import threading
from typing import Any, Optional, Tuple


class AsyncCursor:
    """Thin async wrapper around a sqlite3.Cursor."""

    def __init__(self, conn: "AsyncConnection", cursor: sqlite3.Cursor):
        self._conn = conn
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    async def fetchone(self):
        return await self._conn._run(self._cursor.fetchone)

    async def fetchall(self):
        return await self._conn._run(self._cursor.fetchall)


class AsyncConnection:
    """Runs every sqlite3 call on one dedicated worker thread, so the
    underlying connection is only ever touched sequentially - regardless
    of how many asyncio tasks call into it concurrently."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: "queue.Queue" = queue.Queue()

    def _worker(self, ready_event: threading.Event):
        # isolation_level=None => autocommit mode, so explicit
        # "BEGIN" / commit() / rollback() calls elsewhere in the codebase
        # are the *only* thing controlling transactions (no implicit
        # transaction wrapping by the sqlite3 module fighting with them).
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, isolation_level=None
        )
        ready_event.set()
        while True:
            item = self._queue.get()
            if item is None:
                break
            func, args, kwargs, fut, loop = item
            try:
                result = func(*args, **kwargs)
                loop.call_soon_threadsafe(fut.set_result, result)
            except BaseException as e:  # noqa: BLE001 - forward any error to the awaiter
                loop.call_soon_threadsafe(fut.set_exception, e)
        self._conn.close()

    async def _start(self):
        ready_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker, args=(ready_event,), daemon=True
        )
        self._thread.start()
        # Wait for the connection to actually be open before returning
        await asyncio.get_event_loop().run_in_executor(None, ready_event.wait)
        return self

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._queue.put((func, args, kwargs, fut, loop))
        return await fut

    async def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> AsyncCursor:
        def _do():
            return self._conn.execute(sql, params)

        cursor = await self._run(_do)
        return AsyncCursor(self, cursor)

    async def executescript(self, script: str):
        await self._run(self._conn.executescript, script)

    async def commit(self):
        await self._run(self._conn.commit)

    async def rollback(self):
        await self._run(self._conn.rollback)

    async def close(self):
        # Ask the worker to close the connection and exit its loop
        self._queue.put(None)
        if self._thread is not None:
            await asyncio.get_event_loop().run_in_executor(None, self._thread.join)


async def connect(db_path: str) -> AsyncConnection:
    conn = AsyncConnection(db_path)
    await conn._start()
    return conn


# Re-exported so callers can catch specific sqlite errors without
# importing the stdlib `sqlite3` module themselves.
IntegrityError = sqlite3.IntegrityError
OperationalError = sqlite3.OperationalError
Error = sqlite3.Error
