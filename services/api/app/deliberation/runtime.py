"""Per-run DB session binding for deliberation nodes and tools."""

from contextvars import ContextVar
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

_session_ctx: ContextVar[Optional[AsyncSession]] = ContextVar("deliberation_session", default=None)


def bind_session(session: AsyncSession) -> None:
    _session_ctx.set(session)


def get_session() -> AsyncSession:
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("Deliberation session not bound")
    return session
