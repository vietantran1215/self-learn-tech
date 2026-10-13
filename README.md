# Fieldnotes — self-learn-tech

A local-first learning notebook built with React, TypeScript, Vite, FastAPI, LangChain, LangGraph and Deep Agents. Upload material, ask source-cited questions, practice interview answers, and download study decks as PowerPoint files.

This is a working phase-one development application. Two local accounts demonstrate permission boundaries. Demo mode works without model credentials; live mode adds model-generated answers, semantic embeddings, vision ingestion, adaptive evidence grading and agent-driven learning artifacts.

## Start with Docker

Requires Docker Desktop / Docker Engine with Compose.

```sh
python3 scripts/setup_env.py
docker compose up --build
```

Open **http://localhost:5173**. Sign in as **Alice** or **Bob**, using `learn-local` unless you changed `DEMO_PASSWORD`. Create a notebook, upload `evaluation/source.md`, wait for **ready**, then try chat, interview practice, or study slides. The API documentation is at http://localhost:8000/docs. Nginx resolves the API through Docker DNS at runtime, so recreating the API does not require restarting the frontend.

Uploads return immediately with HTTP 202. A separate worker dispatches the durable outbox to local Kafka and processes the document asynchronously. Queued documents need a running worker and broker; the API does not perform ingestion inline.

## Start with local development processes

Run commands from this repository's root. Python 3.12+ and Node 22.12+ are recommended.

```sh
python3 scripts/setup_env.py
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
.venv/bin/pip install --no-deps -e backend
npm ci --prefix frontend
docker compose up -d kafka
```

In three terminals:

```sh
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```sh
.venv/bin/python -m app.worker
```

```sh
npm run dev --prefix frontend
```

Optional: `.venv/bin/python scripts/seed_demo.py` creates an Alice notebook and uploads the sample source through the API. It still needs Kafka and the worker.

The Docker stack uses named volumes; local Python processes use `data/`. They are separate storage environments. Stop local API/frontend processes before starting the full Docker stack on the same ports.

## Connect live models

Set these values in `.env` and restart **both API and worker**:

```dotenv
DEMO_MODE=false
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
```

The provider must implement OpenAI-compatible chat, tool calls and embeddings. Image ingestion additionally needs a vision-capable chat model. Leave `CHAT_TEMPERATURE` unset to use the provider default; some reasoning models reject a forced temperature of zero. Model names are configurable examples; choose models available from your provider. For Docker, apply changed environment values with `docker compose up -d --force-recreate api worker`.

When switching from demo to live mode, retained source chunks can be migrated without uploading again:

```sh
docker compose stop worker
docker compose exec -e DEMO_MODE=false -T api python - < scripts/reindex_embeddings.py
docker compose up -d --force-recreate api worker
```

The migration updates all ready chunks transactionally after embedding batches succeed. It retains extracted text and existing visual captions; it does not add vision captions to PDFs previously processed in demo mode. Re-upload into a fresh notebook for full live vision extraction, or after other extraction changes. Without this migration, existing chunks retain their previous vectors and visual extraction. Different vector dimensions are rejected. Same-dimension models cannot be automatically distinguished yet.

Demo mode uses deterministic hashed term vectors and returns labelled excerpts. Quizzes and decks in demo mode use excerpts as examples; they are not intelligent model-generated content. Image-only uploads fail with an actionable error in demo mode. Scanned PDFs require live vision mode. Chat transcripts stay in browser memory for the current page session; notebooks, documents, events and generated files persist on the backend.

## Where the requested techniques live

| Technique | Implementation |
| --- | --- |
| Permission-aware RAG | Signed sessions identify the account; notebook ownership is checked on API reads/writes, retrieval, events and downloads. SQLAlchemy retrieval queries constrain candidates by owner and notebook **before** similarity scoring. Agent search tools close over that scope. |
| Multimodal RAG | PDF text plus rendered visual pages, PPTX text plus embedded images, and PNG/JPEG descriptions retain document/page/modality metadata. Vision descriptions and text use the same text embedding index. |
| Adaptive RAG | LangGraph's `plan → search → assess` loop branches on model-assessed evidence sufficiency. |
| Multi-hop reasoning | Initial query decomposition and evidence-driven follow-up queries gather bridge facts; at most three search passes and twelve final chunks. Final generation cites combined evidence and is instructed to acknowledge gaps. |
| Event streaming | Authenticated SSE delivers ingestion events with resumable cursors, graph progress, source references and live answer tokens. |
| LangChain | Model adapters, embeddings, chunk splitting, messages and agent tools. |
| LangGraph | Explicit state, conditional routing, bounded retrieval and streaming in `backend/app/rag.py`. |
| Deep Agents | Live quiz/deck planning and scoped evidence tools in `backend/app/studio.py`. The agent's filesystem state is ephemeral; it has no host filesystem or shell backend. |
| RAGAS component evaluation | Context precision and recall measure initial retrieval against reviewed references. |
| RAGAS end-to-end evaluation | Faithfulness, answer relevancy and factual correctness measure actual graph answers and final evidence. |
| LangSmith | Opt-in trace configuration covers graph/model/tool calls plus explicit retrieval, ingestion and studio spans. |

See [the architecture notes](docs/architecture.md) for the reasoning behind these choices and phase-two work.

## Evaluation and observability

Enable tracing by setting `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`, then restart processes. Source excerpts, prompts and answers may be included in traces sent to LangSmith. Tracing is disabled by default.

The RAGAS runner uses the current API-compatible model as a judge; `--judge-model` can select another available model. It requires live mode and a model key, and incurs model/embedding calls. The sample references are starter fixtures: review them and add real learning questions before using quality thresholds as a release gate.

```sh
# No paid calls: checks dataset shape and installed RAGAS imports.
.venv/bin/python evaluation/run.py --validate-only

# Use a notebook containing evaluation/source.md, processed in live mode.
.venv/bin/python evaluation/run.py --notebook NOTEBOOK_ID --mode components
.venv/bin/python evaluation/run.py --notebook NOTEBOOK_ID --mode all --min-faithfulness 0.8
```

Reports go to `data/evaluation/report.json`, including per-case contexts, responses, hops and mean scores. A threshold failure returns exit code 1. Errors and non-finite scores fail the run. No simulated RAGAS numbers are reported. For Docker-stored notebooks, run the evaluator inside the API container:

```sh
docker compose exec -w /app api python evaluation/run.py --notebook NOTEBOOK_ID
```

## Checks

```sh
.venv/bin/pytest backend/tests -q
npm run build --prefix frontend
npm run test --prefix frontend
.venv/bin/pip check
.venv/bin/python evaluation/run.py --validate-only
```

Tests cover account isolation across retrieval, upload, chat, events, studio and download; idempotent ingestion; failed-upload retry; bounded multi-hop routing; actual Deep Agents tool invocation with a deterministic fake model; visual-description metadata; and worker retry/DLQ commit order. Fake models test plumbing and control flow, not real answer quality.

## First-version boundaries

- Authentication uses two local development accounts and a shared configured password. Replace it with verified OIDC identities, per-user sessions and rate limits before a hosted release. The notebook boundary currently supports private ownership, not collaboration or role-based sharing.
- SQLAlchemy ORM sessions manage persistence over SQLite WAL; local files keep setup understandable. Retrieval scores all authorized chunks in memory; use PostgreSQL/pgvector or a filtered vector service when the corpus grows. Run a single ingestion worker against this shared local database.
- Multimodal retrieval uses vision-to-text descriptions, not joint image/text embeddings. Audio, video, PPTX chart objects and arbitrary formats are outside this phase. Vision transcription and citations need human review.
- Chat generation streams tokens. Quiz and deck creation show a busy state and return complete validated results; they are synchronous HTTP requests in this phase.
- Upload size is capped at 20 MB and PDFs at 2,000 pages by default (`MAX_PDF_PAGES` in `.env`). This is not a hardened untrusted-document processing sandbox. Source instructions are treated as data in prompts, but prompt-injection resistance is not guaranteed.
- Live model calls, LangSmith trace delivery and paid RAGAS scoring need configured credentials. No scores or production-readiness claims are implied by demo-mode checks.

The framework APIs were checked against the official [LangGraph streaming documentation](https://docs.langchain.com/oss/python/langgraph/streaming), [Deep Agents quickstart](https://docs.langchain.com/oss/python/deepagents/quickstart), and [RAGAS metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/).

The Compose frontend waits for the API healthcheck during startup. The browser retries up to three times after an initial 502/503/504 response, before a chat stream begins. Accepted chat streams and other POST operations are not replayed. Document-event streams reconnect after temporary gateway/network failures with their last received cursor.
