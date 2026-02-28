import sqlite3
from typing import NamedTuple


class MemoryData(NamedTuple):
    """
    Represents the data structure for the memory module, containing the following fields:
    - chat_id: An integer representing the identifier for the chat session.
    - user_id: An integer representing the identifier for the user associated with the memory entry.
    - prompt: A string containing a summarize of the prompt or input that led to action taken.
    - tool: A string indicating the tool or method used to generate the response.
    - response: A string containing the response generated based on the prompt and tool.
    - response_code : An integer representing the status code of the response, indicating success or failure of the action taken.
    - timestamp: An integer representing the time when the memory entry was created, typically stored as a
    """
    chat_id: int
    user_id: int
    prompt: str
    tool: str
    response: str
    response_code: int
    timestamp: int


class MemoryModule:
    def __init__(self, user_id, db_path='manuclaw.db'):
        self.conn = sqlite3.connect(db_path)
        self.user_id = user_id
        self.create_table()

    def create_table(self) -> None:
        with self.conn:
            sql = f'''
                CREATE TABLE IF NOT EXISTS memory{self.user_id} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    response TEXT NOT NULL,
                    response_code INTEGER NOT NULL,
                    timestamp INTEGER DEFAULT (strftime('%s', 'now'))
                )
            '''
            self.conn.execute(sql)

    def add_memory(self, data: MemoryData) -> None:
        with self.conn:
            self.conn.execute(f'''
                INSERT INTO memory{data.user_id} (
                    chat_id, user_id, prompt, tool, response, response_code, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.chat_id,
                data.user_id,
                data.prompt,
                data.tool,
                data.response,
                data.response_code,
                data.timestamp
            ))

    def get_memories(self, user_id: int, limit=10) -> list:
        cursor = self.conn.cursor()
        sql = f"""SELECT
            id, chat_id, user_id, prompt, tool, response, response_code, timestamp
            FROM memory{user_id}
            ORDER BY timestamp DESC LIMIT {limit}"""
        cursor.execute(sql)
        return cursor.fetchall()

    def close(self):
        self.conn.close()