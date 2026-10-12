import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from fastapi import HTTPException
from .config import settings

@contextmanager
def db():
    con = sqlite3.connect(settings.data_dir / "app.db", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS notebooks(id TEXT PRIMARY KEY, title TEXT, owner TEXT);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, notebook TEXT, name TEXT, path TEXT, status TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, document TEXT, page INTEGER, text TEXT, modality TEXT, vector TEXT);
        CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, document TEXT, sent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, notebook TEXT, kind TEXT, data TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, notebook TEXT, path TEXT, name TEXT);
        ''')

def uid():
    return str(uuid.uuid4())

def authorize(notebook: str, user: str):
    with db() as c:
        row = c.execute("SELECT * FROM notebooks WHERE id=? AND owner=?", (notebook, user)).fetchone()
    if not row:
        raise HTTPException(404, "Notebook not found")
    return dict(row)

def event(notebook, kind, data):
    with db() as c:
        c.execute("INSERT INTO events(notebook,kind,data,created) VALUES(?,?,?,?)", (notebook, kind, json.dumps(data), time.time()))
