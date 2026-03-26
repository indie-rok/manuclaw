from __future__ import annotations

import sqlite3
import time


class Memory:
    def __init__(self, db_path: str = "manuclaw.db") -> None:
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tool_name TEXT,
                    content TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL
                )
                """
            )

    def save(
        self,
        conversation_id: str,
        role: str,
        content: str,
        iteration: int,
        tool_name: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO memory (conversation_id, role, tool_name, content, iteration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    tool_name,
                    content,
                    iteration,
                    int(time.time()),
                ),
            )

    def get_history(self, conversation_id: str) -> list[dict[str, object | None]]:
        cursor = self.connection.execute(
            """
            SELECT conversation_id, role, tool_name, content, iteration, timestamp
            FROM memory
            WHERE conversation_id = ?
            ORDER BY iteration ASC, timestamp ASC, id ASC
            """,
            (conversation_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self.connection.close()
