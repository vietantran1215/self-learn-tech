import base64
import json
from langsmith import traceable
from pathlib import Path
import pymupdf as fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pptx import Presentation
from .config import settings
from .models import llm, embed, content_text
from .store import db, event, uid

async def describe_image(raw: bytes, mime: str):
    if settings.demo_mode:
        raise ValueError("Image understanding requires live mode and a vision-capable model")
    result = await llm().ainvoke([{"role":"user","content":[
        {"type":"text","text":"Transcribe this image and describe diagrams, charts, labels and relationships precisely. Do not invent unreadable content."},
        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{base64.b64encode(raw).decode()}"}}
    ]}])
    return content_text(result)

async def extract(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return [(1,path.read_text(encoding="utf-8"),"text")]
    if suffix in {".png", ".jpg", ".jpeg"}:
        return [(1, await describe_image(path.read_bytes(),"image/png" if suffix==".png" else "image/jpeg"),"image")]
    if suffix == ".pptx":
        deck = Presentation(path)
        pages=[]
        for i,slide in enumerate(deck.slides,1):
            pages.append((i,"\n".join(s.text for s in slide.shapes if s.has_text_frame),"text"))
            for shape in slide.shapes:
                if shape.shape_type == 13 and not settings.demo_mode:
                    pages.append((i,await describe_image(shape.image.blob,shape.image.content_type),"image"))
        return pages
    if suffix == ".pdf":
        pages=[]
        with fitz.open(path) as doc:
            if len(doc)>100:
                raise ValueError("Maximum 100 PDF pages")
            for i,page in enumerate(doc,1):
                text=page.get_text()
                if text.strip():
                    pages.append((i,text,"text"))
                # Render pages with visual content (including scanned PDFs) for vision retrieval.
                if not settings.demo_mode and (page.get_images() or page.get_drawings() or not text.strip()):
                    pages.append((i,await describe_image(page.get_pixmap(matrix=fitz.Matrix(1,1)).tobytes("png"),"image/png"),"image"))
        return pages
    raise ValueError("Unsupported document format")

@traceable(name="document-ingestion")
async def ingest(document):
    with db() as c:
        row=c.execute("SELECT * FROM documents WHERE id=?",(document,)).fetchone()
        if not row or row["status"]=="ready":
            return
        c.execute("UPDATE documents SET status='processing',error=NULL WHERE id=?",(document,))
    event(row["notebook"],"ingestion",{"document":document,"status":"processing"})
    try:
        pages=await extract(Path(row["path"]))
        splitter=RecursiveCharacterTextSplitter(chunk_size=1200,chunk_overlap=200)
        chunks=[(page,text,modality) for page,body,modality in pages for text in splitter.split_text(body) if text.strip()]
        if not chunks:
            raise ValueError("No readable content. Scanned PDFs require live vision mode.")
        vectors=await embed([text for _,text,_ in chunks])
        with db() as c:
            c.execute("DELETE FROM chunks WHERE document=?",(document,))
            c.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?)",[(uid(),document,p,t,m,json.dumps(v)) for (p,t,m),v in zip(chunks,vectors)])
            c.execute("UPDATE documents SET status='ready' WHERE id=?",(document,))
        event(row["notebook"],"ingestion",{"document":document,"status":"ready","chunks":len(chunks)})
    except Exception as exc:
        with db() as c:
            c.execute("UPDATE documents SET status='failed',error=? WHERE id=?",(str(exc)[:500],document))
        event(row["notebook"],"ingestion",{"document":document,"status":"failed"})
        raise
