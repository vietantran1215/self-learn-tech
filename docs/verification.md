# Verification — 13 October 2026

- Frontend TypeScript check and Vite production build passed.
- Eight backend tests passed locally and inside the Python 3.12 Docker image.
- Dependency check passed. RAGAS 0.4.3 imports and three dataset fixtures validated.
- Full Compose stack started: frontend, API, Kafka and ingestion worker.
- Sample upload submitted over HTTP, persisted in the outbox, published to Kafka and processed by the worker into ready chunks.
- Container-hosted chat completed its SSE stream. Generated PPTX downloaded and opened with python-pptx. Another account's artifact download returned 404.
- Browser checks covered login, notebook view, source-cited chat, answer/rubric reveal and slide generation. A clipped header and workspace sizing were corrected during review.
- Sample PowerPoint was rendered with LibreOffice. Independent visual review found font substitution, raw Markdown, partial words and footer sizing issues. A revised render passed review with no overlap or clipping.

Live-provider checks subsequently passed using the configured OpenAI-compatible gateway and `gpt-6-luna`:

- Chat connectivity succeeded after removing the forced temperature of zero.
- All 184 ready chunks were migrated to real `text-embedding-3-small` embeddings.
- A source-grounded chat answer completed three retrieval passes and returned citations to the uploaded book.
- Deep Agents generated three interview questions and a three-slide study deck; the downloaded PPTX passed structural validation.
- The earlier rendered-layout review applies to the renderer/template; the newly generated live deck has not had a separate rendered visual review.

Real vision transcription, LangSmith trace delivery and paid RAGAS scoring remain **unverified**. Previously demo-ingested PDFs retain their extracted text; embedding migration does not backfill image descriptions. Deterministic fake models exercise graph branching, Deep Agents tools and multimodal metadata but do not establish semantic answer quality. This is a local development application, not a production security assessment.

## SQLAlchemy transition

- Replaced raw application SQL in API endpoints, ingestion, permission-aware retrieval, artifact persistence, Kafka outbox dispatch and embedding maintenance with SQLAlchemy mapped models and sessions.
- Twelve tests passed locally and in the Python 3.12 container, including legacy-schema/JSON compatibility, atomic document/outbox rollback, and Kafka acknowledgement ordering.
- Took a SQLite backup before deployment. Every pre-update record across all six tables remained unchanged after deployment; uploads created during the transition were retained as additional records.
- Live retrieval, authenticated listings, SSE cursor requests, artifact download and cross-account denial passed through the running Nginx/API stack.

## Gateway recovery

The reported chat 502 coincided with the API replacement during the ORM deployment. Replaying the `alo` request through Nginx returned HTTP 200 and a complete LLM stream. Added an API healthcheck and frontend startup readiness dependency, bounded gateway retries before chat stream acceptance, cancellation-aware backoff, and durable-event reconnection. Six frontend recovery tests and the production build passed; Compose reported the API healthy after deployment.
