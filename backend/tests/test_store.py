"""Behavior and compatibility checks for the SQLAlchemy persistence transition."""
import json
import sqlite3
import pytest
from sqlalchemy import select, func
from app.config import settings
from app.db_models import NotebookRecord, DocumentRecord, OutboxRecord, ChunkRecord, IngestionEvent
from app.store import db, init, authorize, event


def test_transaction_rolls_back_document_and_outbox_together(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',tmp_path)
    init()
    with db() as session:
        session.add(NotebookRecord(id='notebook',title='Rollback',owner='alice'))
    with pytest.raises(RuntimeError):
        with db() as session:
            session.add(DocumentRecord(id='doc',notebook='notebook',name='a.txt',path='a.txt',status='queued'))
            session.flush()
            session.add(OutboxRecord(id='job',document='doc'))
            session.flush()
            raise RuntimeError('Simulated failure before transaction commit')
    with db() as session:
        assert session.get(DocumentRecord,'doc') is None
        assert session.scalar(select(func.count()).select_from(OutboxRecord))==0
    # A new session can commit after the failed transaction.
    event('notebook','check',{'status':'ok'})
    with db() as session:
        assert session.scalar(select(IngestionEvent)).data=={'status':'ok'}


def test_existing_sqlite_schema_and_json_remain_readable(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'data_dir',tmp_path)
    # Deliberately construct the OLD database through sqlite3 to prove ORM compatibility.
    with sqlite3.connect(tmp_path/'app.db') as old:
        old.executescript('''
          CREATE TABLE notebooks(id TEXT PRIMARY KEY,title TEXT,owner TEXT);
          CREATE TABLE documents(id TEXT PRIMARY KEY,notebook TEXT,name TEXT,path TEXT,status TEXT,error TEXT);
          CREATE TABLE chunks(id TEXT PRIMARY KEY,document TEXT,page INTEGER,text TEXT,modality TEXT,vector TEXT);
          CREATE TABLE outbox(id TEXT PRIMARY KEY,document TEXT,sent INTEGER DEFAULT 0);
          CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,notebook TEXT,kind TEXT,data TEXT,created REAL);
          CREATE TABLE artifacts(id TEXT PRIMARY KEY,notebook TEXT,path TEXT,name TEXT);
        ''')
        old.execute('INSERT INTO notebooks VALUES(?,?,?)',('n','Existing notebook','alice'))
        old.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',('d','n','notes.md','notes.md','ready',None))
        old.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',('c','d',115,'Retained source text','text',json.dumps([.1,.2])))
        old.execute('INSERT INTO events VALUES(?,?,?,?,?)',(12,'n','ingestion',json.dumps({'status':'ready'}),1.0))
    init() # create_all must not recreate or clear the old tables.
    assert authorize('n','alice')['title']=='Existing notebook'
    with pytest.raises(Exception) as exc:authorize('n','bob')
    assert exc.value.status_code==404
    with db() as session:
        chunk=session.get(ChunkRecord,'c')
        assert chunk.vector==[.1,.2] and chunk.page==115
        assert session.get(IngestionEvent,12).data=={'status':'ready'}
        chunk.vector=[.3,.4] # ORM writes remain compatible with the stored JSON encoding.
    event('n','ingestion',{'status':'updated'})
    with db() as session:
        assert session.get(ChunkRecord,'c').vector==[.3,.4]
        assert session.scalar(select(func.max(IngestionEvent.id)))==13

@pytest.mark.asyncio
async def test_outbox_is_marked_sent_only_after_kafka_ack(tmp_path,monkeypatch):
    from app import worker
    monkeypatch.setattr(settings,'data_dir',tmp_path)
    init()
    with db() as session:
        session.add(NotebookRecord(id='n',title='Outbox',owner='alice'))
        session.flush()
        session.add(DocumentRecord(id='d',notebook='n',name='a.md',path='a.md',status='queued'))
        session.flush()
        session.add(OutboxRecord(id='job',document='d'))
    class Producer:
        fail=True
        async def send_and_wait(self,topic,payload,key):
            assert topic=='document.uploaded' and json.loads(payload)=={'document':'d'} and key==b'd'
            if self.fail:raise RuntimeError('Broker unavailable')
    producer=Producer()
    with pytest.raises(RuntimeError,match='Broker unavailable'):
        await worker.dispatch(producer)
    with db() as session:assert session.get(OutboxRecord,'job').sent==0
    producer.fail=False
    async def stop_after_pass(_):raise worker.asyncio.CancelledError()
    monkeypatch.setattr(worker.asyncio,'sleep',stop_after_pass)
    with pytest.raises(worker.asyncio.CancelledError):await worker.dispatch(producer)
    with db() as session:assert session.get(OutboxRecord,'job').sent==1
