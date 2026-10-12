# How this learning notebook works

The user's material is the evidence base. The application should make it easy to ask questions and check the sources, then turn understanding into practice.

## Upload path

1. FastAPI verifies the session and notebook owner, writes the uploaded bytes, and atomically records the document and an outbox entry in SQLite.
2. The ingestion worker publishes pending outbox entries to `document.uploaded`. It marks each entry sent only after Kafka acknowledges it.
3. The consumer extracts pages, captions visual material in live mode, splits the content, embeds it, and transactionally replaces that document's chunks.
4. Duplicate delivery of a ready document is a no-op. Failed documents are retried up to three times. An exhausted job is published to `document.failed` before its offset is committed. The UI shows document errors and supports manual retry.
5. Durable ingestion events reach the browser over authenticated SSE. Reconnection resumes from the last received event ID.

The broker uses one local KRaft node. API and worker share a data volume; Kafka has its own persistent volume. This is an at-least-once flow, not an exactly-once distributed transaction. Multiple replicas need database-backed job leases, partition-aware concurrency and a scalable storage design. File writes preceding a failed database transaction may need periodic orphan cleanup in a production implementation.

## Chat path

The server captures notebook and account identity before graph execution. The planner resolves conversational references and splits a question into up to three search queries. Every search authorizes the notebook and restricts SQL candidates by owner before vector comparison.

The evidence grader decides whether another fact is needed. A follow-up search uses the current evidence to formulate the next query. The graph repeats for at most three passes and keeps at most twelve evidence chunks, then generates a cited answer. Its stream exposes useful progress, evidence and answer tokens; it does not expose a private chain of thought.

This is bounded evidence gathering. It does not prove that every answer is correct. RAGAS and human source review measure how well retrieval and generation actually work.

## Learning studio

A Deep Agent receives the topic, evidence and a schema. It can plan and call a tool to retrieve more authorized evidence. That tool has no user or notebook argument: identity comes from the server closure. Quiz answers include rubrics and evidence indexes; learners answer before revealing them.

Deck output is validated, then rendered with deterministic PowerPoint geometry. Bullets are capped for the available slide slots. Source references appear on slides; fuller excerpts are stored in speaker notes. Download authorization checks the artifact's notebook ownership. The renderer is a starting design template, not a full presentation design system.

## Evaluate each layer

Initial context precision and recall tell us whether retrieval finds useful evidence. Faithfulness checks whether the final answer is supported by the final evidence. Answer relevancy measures whether it addresses the question. Factual correctness compares it with a reviewed reference. Use both per-case scores and aggregate scores; a good mean can hide individual failures.

Permission isolation is tested deterministically. An LLM judge cannot replace an authorization test. Vision extraction needs dedicated chart/diagram fixtures and human review; text faithfulness alone cannot establish image understanding quality. Add separate quiz/deck quality fixtures in the next phase.

LangSmith connects traces across model calls, graph nodes and tools. It is opt-in because prompts and document material can be sensitive. Use per-tenant tracing policies and redaction before extending the application to shared organizational documents.

## Sensible next steps

After trying the first version, refine the learning experience around real material. The next iteration should add persistent conversation history and interview feedback, move studio requests to background jobs with progress events, and support document deletion with index cleanup. Then add OIDC, explicit notebook membership and revocation tests, database-backed job leases, a filtered vector index, and a larger human-reviewed evaluation dataset.

Each addition should solve an observed need. The initial architecture keeps each requested technique visible without turning every user action into a complex agent run.
