"""Re-embed retained extracted chunks when switching models or leaving demo mode.

Run against the same data volume as the API, with ingestion paused. This preserves
uploaded files, document IDs, page references and extracted text/visual captions.
It does not add vision captions to documents originally ingested in demo mode.
"""
import argparse
import asyncio
from sqlalchemy import select, update
from app.db_models import ChunkRecord, DocumentRecord
from app.config import settings
from app.models import embed
from app.store import db, init, event

async def reindex(notebook=None):
    if settings.demo_mode:
        raise ValueError('Set DEMO_MODE=false before creating live embeddings')
    if not settings.openai_api_key:
        raise ValueError('OPENAI_API_KEY is required')
    init()
    with db() as c:
        query=select(ChunkRecord,DocumentRecord.notebook).join(DocumentRecord,DocumentRecord.id==ChunkRecord.document).where(DocumentRecord.status=='ready')
        if notebook:
            query=query.where(DocumentRecord.notebook==notebook)
        rows=c.execute(query).all()
    updates=[]
    for start in range(0,len(rows),64):
        batch=rows[start:start+64]
        vectors=await embed([row.text for row,_ in batch])
        if len(vectors)!=len(batch):
            raise ValueError('Embedding endpoint returned an incomplete batch')
        updates.extend({'id':r.id,'vector':v} for (r,_),v in zip(batch,vectors))
        print(f'Embedded {min(start+64,len(rows))}/{len(rows)} chunks',flush=True)
    # Keep the existing index intact if any provider request fails.
    with db() as c:
        if updates:
            c.execute(update(ChunkRecord),updates)
    for n in {n for _,n in rows}:
        event(n,'reindexed',{'status':'ready','embedding_model':settings.embedding_model})
    print(f'Updated {len(updates)} chunks using {settings.embedding_model}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--notebook',help='Limit migration to one notebook; omit for the full local index')
    args=p.parse_args()
    asyncio.run(reindex(args.notebook))
