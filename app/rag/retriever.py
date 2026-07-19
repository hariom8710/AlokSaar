"""
RAG Engine — Retrieval-Augmented Generation over the pharmacy knowledge base.

Uses ChromaDB as the vector store (as specified in the project doc). Chroma's
default embedding function (all-MiniLM-L6-v2 via sentence-transformers) is
used so the pipeline works out of the box without requiring an external
embeddings API call. On first run, Chroma downloads this small model —
requires normal internet access. If that download fails or is blocked
(restricted network, firewall, flaky connection), the rest of the app
still works: retrieve() will just return no results rather than crashing
startup, so the dashboard, chat's business-data answers, and everything
else remain usable — only medicine/compliance RAG lookups are affected.
"""
import chromadb
from app.rag.knowledge_documents import KNOWLEDGE_DOCUMENTS

_client = None
_collection = None
_init_error = None

COLLECTION_NAME = "aloksaar_knowledge_base"


def _get_client(persist_path: str):
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=persist_path)
    return _client


def init_knowledge_base(persist_path: str, force_reseed: bool = False):
    """Initialize (and if empty, seed) the ChromaDB collection. Never raises
    — logs and stores the error instead, so app startup always succeeds
    even if the embedding model download fails (e.g. restricted network)."""
    global _collection, _init_error
    try:
        client = _get_client(persist_path)

        if force_reseed:
            try:
                client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass

        _collection = client.get_or_create_collection(name=COLLECTION_NAME)

        if _collection.count() == 0:
            _collection.add(
                ids=[doc["id"] for doc in KNOWLEDGE_DOCUMENTS],
                documents=[doc["text"] for doc in KNOWLEDGE_DOCUMENTS],
                metadatas=[{"category": doc["category"]} for doc in KNOWLEDGE_DOCUMENTS],
            )
        _init_error = None
        return _collection
    except Exception as e:
        _collection = None
        _init_error = str(e)
        print(
            f"[AlokSaar] WARNING: RAG knowledge base failed to initialize "
            f"({e}). The app will still run — dashboard, chat business "
            f"answers, and everything else work normally. Only "
            f"medicine/compliance knowledge-base lookups will be "
            f"unavailable until this is resolved (usually a network issue "
            f"downloading Chroma's embedding model — check your internet "
            f"connection and try restarting)."
        )
        return None


def is_available() -> bool:
    return _collection is not None


def retrieve(query: str, n_results: int = 3) -> list:
    """Semantic search over the knowledge base. Returns list of {text, category,
    relevance}. Returns an empty list (never raises) if the knowledge base
    failed to initialize — callers already treat an empty result as 'no RAG
    context available' and degrade gracefully."""
    if _collection is None:
        return []

    try:
        results = _collection.query(query_texts=[query], n_results=n_results)
    except Exception:
        return []

    out = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for text, meta, dist in zip(docs, metas, dists):
        out.append({
            "text": text,
            "category": meta.get("category") if meta else None,
            "relevance": round(1 - dist, 3) if dist is not None else None,
        })
    return out
