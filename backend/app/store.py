import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import create_engine, event as engine_event, select
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session
from .config import settings
from .db_models import Base, IngestionEvent, NotebookRecord


@lru_cache(maxsize=16)
def _engine(path: str) -> Engine:
    engine = create_engine(
        URL.create('sqlite+pysqlite', database=path),
        connect_args={'timeout': 30, 'check_same_thread': False},
    )

    @engine_event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        # Driver SQL is limited to SQLite connection settings, not application queries.
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

    return engine


def get_engine() -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return _engine(str((settings.data_dir / 'app.db').resolve()))


@contextmanager
def db():
    """One short-lived ORM session/transaction; rollback automatically on failure.

    Do not retain a session across model calls, Kafka acknowledgements or SSE waits.
    Loaded fields remain usable after commit/close; no lazy relationships are exposed.
    """
    with Session(get_engine(), expire_on_commit=False) as session:
        with session.begin():
            yield session


def init():
    Base.metadata.create_all(get_engine())


def uid():
    return str(uuid.uuid4())


def authorize(notebook: str, user: str):
    with db() as session:
        record = session.scalar(select(NotebookRecord).where(
            NotebookRecord.id == notebook, NotebookRecord.owner == user))
        if record is None:
            raise HTTPException(404, 'Notebook not found')
        return {'id': record.id, 'title': record.title, 'owner': record.owner}


def event(notebook, kind, data):
    with db() as session:
        session.add(IngestionEvent(notebook=notebook, kind=kind, data=data, created=time.time()))
