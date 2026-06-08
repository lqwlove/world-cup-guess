"""LangGraph checkpointer backed by PostgreSQL (with in-memory fallback)."""

import asyncio
import logging
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_checkpointer: Optional[Any] = None
_pool: Optional[Any] = None
_setup_done = False


async def get_checkpointer() -> Any:
    global _checkpointer, _pool, _setup_done
    if _checkpointer is not None:
        return _checkpointer

    if not settings.graph_checkpoint_enabled:
        logger.warning("Graph checkpoint disabled; using MemorySaver")
        _checkpointer = MemorySaver()
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        _pool = AsyncConnectionPool(
            conninfo=settings.database_url_sync,
            max_size=10,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        await asyncio.wait_for(_pool.open(), timeout=5.0)
        saver = AsyncPostgresSaver(_pool)
        if not _setup_done:
            await asyncio.wait_for(saver.setup(), timeout=10.0)
            _setup_done = True
        _checkpointer = saver
        logger.info("Using AsyncPostgresSaver (pool) for LangGraph checkpoints")
    except Exception as exc:
        logger.warning("Postgres checkpointer unavailable (%s); using MemorySaver", exc)
        if _pool is not None:
            try:
                await _pool.close()
            except Exception:
                pass
        _pool = None
        _checkpointer = MemorySaver()

    return _checkpointer
