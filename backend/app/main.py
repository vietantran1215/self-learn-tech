import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from .auth import user, issue
from .config import settings
from .store import init, db, authorize, uid
from .rag import rag_graph
from .studio import generate, export_deck

@asynccontextmanager
async def lifespan(app):
    init()
    yield

app=FastAPI(title='Self Learn Tech',lifespan=lifespan)
log=logging.getLogger(__name__)
class Login(BaseModel):
    username: Literal['alice','bob']
    password: str
class Notebook(BaseModel):
    title: str = Field(min_length=1,max_length=120)
class Message(BaseModel):
    role: Literal['user','assistant']
    content: str = Field(max_length=12000)
class Chat(BaseModel):
    question: str = Field(min_length=1,max_length=4000)
    history: list[Message] = Field(default_factory=list,max_length=8)
class Studio(BaseModel):
    topic: str = Field(min_length=1,max_length=500)

def sse(data):
    return 'data: '+json.dumps(data)+'\n\n'

@app.get('/api/health')
def health():
    return {'status':'ok','demo_mode':settings.demo_mode,'vision':not settings.demo_mode,'auth':'local-development'}

@app.post('/api/login')
def login(body: Login):
    # Local development accounts. Replace with verified OIDC identities for production.
    if not hmac.compare_digest(body.password,settings.demo_password):
        raise HTTPException(401,'Invalid credentials')
    return {'token':issue(body.username),'user':body.username}

@app.get('/api/notebooks')
def notebooks(identity=Depends(user)):
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM notebooks WHERE owner=? ORDER BY rowid DESC',(identity,))]

@app.post('/api/notebooks',status_code=201)
def create(body: Notebook,identity=Depends(user)):
    id=uid()
    with db() as c:
        c.execute('INSERT INTO notebooks VALUES(?,?,?)',(id,body.title,identity))
    return {'id':id,'title':body.title,'owner':identity}

@app.get('/api/notebooks/{notebook}/documents')
def documents(notebook: str,identity=Depends(user)):
    authorize(notebook,identity)
    with db() as c:
        return [dict(r) for r in c.execute('SELECT id,name,status,error FROM documents WHERE notebook=?',(notebook,))]

@app.post('/api/notebooks/{notebook}/documents',status_code=202)
async def upload(notebook: str,file: UploadFile,identity=Depends(user)):
    authorize(notebook,identity)
    name=Path(file.filename or 'document').name
    suffix=Path(name).suffix.lower()
    if suffix not in {'.txt','.md','.pdf','.pptx','.png','.jpg','.jpeg'}:
        raise HTTPException(415,'Use PDF, TXT, Markdown, PPTX, PNG or JPEG')
    id=uid()
    path=settings.data_dir / f'{id}{suffix}'
    size=0
    try:
        with path.open('wb') as out:
            while chunk:=await file.read(65536):
                size+=len(chunk)
                if size>20*1024*1024:
                    raise HTTPException(413,'Maximum upload size is 20 MB')
                out.write(chunk)
        if size==0:
            raise HTTPException(400,'Empty file')
        with db() as c:
            c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(id,notebook,name,str(path),'queued',None))
            c.execute('INSERT INTO outbox(id,document) VALUES(?,?)',(uid(),id))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {'id':id,'name':name,'status':'queued'}

@app.post('/api/notebooks/{notebook}/documents/{document}/retry',status_code=202)
def retry(notebook: str,document: str,identity=Depends(user)):
    authorize(notebook,identity)
    with db() as c:
        row=c.execute("SELECT status FROM documents WHERE id=? AND notebook=?",(document,notebook)).fetchone()
        if not row:
            raise HTTPException(404,'Document not found')
        if row['status']!='failed':
            raise HTTPException(409,'Only failed uploads can be retried')
        c.execute("UPDATE documents SET status='queued',error=NULL WHERE id=?",(document,))
        c.execute('INSERT INTO outbox(id,document) VALUES(?,?)',(uid(),document))
    return {'status':'queued'}

@app.get('/api/notebooks/{notebook}/events')
async def events(notebook: str,after: int=0,identity=Depends(user)):
    authorize(notebook,identity)
    async def stream():
        cursor=after
        # Short streams reconnect with cursor; permits expired sessions to be rechecked.
        for _ in range(25):
            authorize(notebook,identity)
            with db() as c:
                rows=c.execute('SELECT * FROM events WHERE notebook=? AND id>? ORDER BY id',(notebook,cursor)).fetchall()
            for row in rows:
                cursor=row['id']
                yield sse({'type':'ingestion','id':cursor,**json.loads(row['data'])})
            yield ': heartbeat\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/notebooks/{notebook}/chat')
async def chat(notebook: str,body: Chat,identity=Depends(user)):
    authorize(notebook,identity)
    async def stream():
        try:
            async for event in rag_graph.astream({'user':identity,'notebook':notebook,'question':body.question,'history':[m.model_dump() for m in body.history]},stream_mode='custom'):
                yield sse(event)
            yield sse({'type':'done'})
        except Exception:
            log.exception('Chat failed')
            yield sse({'type':'error','text':'The request failed. Check model configuration and server logs.'})
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/notebooks/{notebook}/quiz')
async def quiz(notebook: str,body: Studio,identity=Depends(user)):
    authorize(notebook,identity)
    try:
        output,hits=await generate(notebook,identity,body.topic,'quiz')
        return {**output.model_dump(),'sources':hits,'demo':settings.demo_mode}
    except ValueError as exc:
        raise HTTPException(422,str(exc))

@app.post('/api/notebooks/{notebook}/deck')
async def deck(notebook: str,body: Studio,identity=Depends(user)):
    authorize(notebook,identity)
    try:
        output,hits=await generate(notebook,identity,body.topic,'deck')
        artifact=export_deck(output,hits,notebook)
        return {'id':artifact,'title':output.title,'slides':output.model_dump()['slides'],'demo':settings.demo_mode}
    except ValueError as exc:
        raise HTTPException(422,str(exc))

@app.get('/api/artifacts/{artifact}')
def download(artifact: str,identity=Depends(user)):
    with db() as c:
        row=c.execute('SELECT * FROM artifacts WHERE id=?',(artifact,)).fetchone()
    if not row:
        raise HTTPException(404,'Artifact not found')
    authorize(row['notebook'],identity)
    return FileResponse(row['path'],filename=row['name'],media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
