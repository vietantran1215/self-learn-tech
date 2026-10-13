import hashlib
import math
import re
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .config import settings

def llm():
    if not settings.openai_api_key:
        raise RuntimeError("Configure OPENAI_API_KEY or enable DEMO_MODE")
    return ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key, base_url=settings.openai_base_url, temperature=settings.chat_temperature, timeout=60)

def demo_vector(text):
    v = [0.0]*256
    for word in re.findall(r"\w+",text.lower()):
        v[int(hashlib.sha256(word.encode()).hexdigest()[:8],16)%256] += 1
    norm = math.sqrt(sum(x*x for x in v)) or 1
    return [x/norm for x in v]

async def embed(texts):
    if settings.demo_mode:
        return [demo_vector(t) for t in texts]
    return await OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key, base_url=settings.openai_base_url).aembed_documents(texts)

def content_text(message):
    if isinstance(message.content, str):
        return message.content
    return "".join(x.get("text","") for x in message.content if isinstance(x,dict))
