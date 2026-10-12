"""Upload sample material through the API; the Kafka worker must ingest it."""
from pathlib import Path
import httpx

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as client:
    from app.config import settings
    r=client.post('/api/login',json={'username':'alice','password':settings.demo_password});r.raise_for_status()
    client.headers['Authorization']='Bearer '+r.json()['token']
    r=client.post('/api/notebooks',json={'title':'Building thoughtful AI applications'});r.raise_for_status()
    notebook=r.json()['id']
    r=client.post(f'/api/notebooks/{notebook}/documents',files={'file':('architecture.md',Path('evaluation/source.md').read_bytes(),'text/markdown')});r.raise_for_status()
    print(f'Created notebook {notebook}; upload status: {r.json()["status"]}')
