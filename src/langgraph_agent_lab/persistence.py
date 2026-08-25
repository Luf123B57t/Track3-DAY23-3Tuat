"""Checkpointer adapter.

Mô-đun quản lý bộ lưu trữ trạng thái (Checkpointer Adapter) cho LangGraph workflow.
Cho phép lưu trữ checkpoint của đồ thị trong bộ nhớ (MemorySaver) hoặc cơ sở dữ liệu (SqliteSaver),
giúp workflow có khả năng khôi phục trạng thái (Resume / State Persistence).
"""

from __future__ import annotations

import sqlite3
from typing import Any


def build_checkpointer(
    kind: str = "memory", database_url: str | None = None
) -> Any | None:  # noqa: ANN401
    """Tạo đối tượng LangGraph checkpointer tương ứng với loại cấu hình.

    Các loại hỗ trợ (`kind`):
    - "none": Trả về None (không lưu trữ trạng thái)
    - "memory": Trả về MemorySaver (lưu trạng thái tạm thời trong RAM)
    - "sqlite": Trả về SqliteSaver (lưu trạng thái bền vững vào SQLite database)
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

