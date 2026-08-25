"""Checkpointer adapter."""

from __future__ import annotations

import sqlite3
from typing import Any


def build_checkpointer(
    kind: str = "memory", database_url: str | None = None
) -> Any | None:  # noqa: ANN401
    """Return a LangGraph checkpointer.

    Supported kinds:
    - "none": returns None (no persistence)
    - "memory": returns MemorySaver
    - "sqlite": returns SqliteSaver using sqlite3 connection
    """
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            msg = "Install langgraph-checkpoint-sqlite: pip install langgraph-checkpoint-sqlite"
            raise RuntimeError(msg) from exc

        db_path = ":memory:"
        if database_url:
            db_path = database_url.replace("sqlite:///", "").replace("sqlite://", "")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return SqliteSaver(conn=conn)
    if kind == "postgres":
        raise NotImplementedError(
            "Postgres checkpointer is not enabled in this lab environment."
        )
    raise ValueError(f"Unknown checkpointer kind: {kind}")
