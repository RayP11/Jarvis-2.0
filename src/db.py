import sqlite3
from langchain.memory import ConversationBufferMemory

DB_FILE = "jarvis_memory.db"
TOKEN_LIMIT = 2000

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)


def _init_db():
    with sqlite3.connect(DB_FILE) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
                user_input  TEXT,
                ai_output   TEXT
            )
        """)


def _load_db():
    with sqlite3.connect(DB_FILE) as c:
        rows = c.execute(
            "SELECT user_input, ai_output FROM memory ORDER BY id DESC LIMIT ?",
            (TOKEN_LIMIT,),
        ).fetchall()[::-1]
    for u, a in rows:
        memory.save_context({"input": f"{u}"}, {"output": f"{a}"})


def _save_entry(u: str, a: str):
    with sqlite3.connect(DB_FILE) as c:
        c.execute(
            "INSERT INTO memory (user_input, ai_output) VALUES (?, ?)",
            (u, a),
        )


_init_db()
_load_db()
