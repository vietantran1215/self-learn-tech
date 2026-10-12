# Learning application architecture

Kafka stores events durably. Consumers commit offsets after successful processing. Committing an offset before processing could mark an unprocessed event as complete. A crash before committing may cause redelivery, so processing must be idempotent.

The server derives the user identity from a verified session. Notebook retrieval restricts candidates to the user's authorized notebook before vector scoring. Every follow-up search uses the same authorization boundary; agents cannot select another identity through their tool arguments.

Adaptive retrieval assesses evidence sufficiency after a search. If evidence is incomplete, the graph creates follow-up queries based on retrieved facts to find missing bridge facts. It stops after at most three retrieval passes and answers from the combined evidence. Remaining uncertainty must be acknowledged.

Ingestion converts text and visual descriptions into chunks. Each chunk retains document, page and modality metadata. Text embeddings let a text query retrieve both original text and image descriptions; this approach is not a native joint image/text embedding model.
