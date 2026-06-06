"""
chroma_store.py
---------------
ChromaDB vector-store integration for monthly incident summary reports.

ChromaDB runs fully **in-process** — no server, no Docker, no cloud account.
Data is persisted to a local directory (default: ./chroma_db) so historical
reports survive between runs.

Responsibilities
----------------
1. Initialise a persistent ChromaDB collection using env / defaults.
2. Serialise a monthly pivot-table row into a text document and upsert it.
3. Expose similarity search over stored reports —
   used by the AgentExecutor tool in agent.py.

Environment Variables (all optional)
-------------------------------------
CHROMA_PERSIST_DIR  Local directory for persistent storage (default: ./chroma_db)
CHROMA_COLLECTION   Collection name (default: "incident_monthly_summaries")

EMBEDDINGS NOTE
---------------
Uses HuggingFace sentence-transformers/all-MiniLM-L6-v2.
Runs fully locally — no API key, no quota, no cost.
Model is downloaded once (~80 MB) and cached in ~/.cache/huggingface.
"""

from __future__ import annotations

import logging
import os
import ssl
from datetime import datetime

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_huggingface import HuggingFaceEmbeddings

from incident_processor import monthly_row_to_text

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from environment with sensible defaults)
# ---------------------------------------------------------------------------

_DEFAULT_PERSIST_DIR = "./chroma_db"
_DEFAULT_COLLECTION = "incident_monthly_summaries"


def _get_config() -> dict[str, str]:
    return {
        "persist_dir": os.environ.get("CHROMA_PERSIST_DIR", _DEFAULT_PERSIST_DIR),
        "collection": os.environ.get("CHROMA_COLLECTION", _DEFAULT_COLLECTION),
    }


# ---------------------------------------------------------------------------
# Embeddings factory
# ---------------------------------------------------------------------------

def _build_embeddings() -> HuggingFaceEmbeddings:
    """
    Build the embeddings model using a local HuggingFace sentence-transformer.

    No API key required.  Model (~80 MB) is downloaded once and cached.
    Uses: sentence-transformers/all-MiniLM-L6-v2
    """
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


# ---------------------------------------------------------------------------
# Vector store factory
# ---------------------------------------------------------------------------

def get_vector_store() -> Chroma:
    """
    Return a persistent Chroma vector store instance.

    The collection is created automatically on first use.
    Data is stored locally under CHROMA_PERSIST_DIR (default: ./chroma_db).
    """
    cfg = _get_config()
    embeddings = _build_embeddings()

    logger.info(
        "Opening Chroma store at '%s', collection='%s'",
        cfg["persist_dir"],
        cfg["collection"],
    )

    store = Chroma(
        collection_name=cfg["collection"],
        embedding_function=embeddings,
        persist_directory=cfg["persist_dir"],
    )
    return store


# ---------------------------------------------------------------------------
# Store operations
# ---------------------------------------------------------------------------

def store_monthly_summary(
    monthly_df: pd.DataFrame,
    vector_store: Chroma | None = None,
) -> None:
    """
    Upsert all rows from the monthly pivot table into ChromaDB.

    Each row becomes one Document:
      - page_content = human-readable summary text (embedded for similarity search)
      - metadata     = {month, ingested_at, per-category counts}

    Uses the month string as the document ID to allow idempotent upserts
    (re-running with the same data won't create duplicates).

    Parameters
    ----------
    monthly_df : pd.DataFrame
        Output of ``aggregate_by_month()`` — index is 'month' (YYYY-MM strings).
    vector_store : Chroma | None
        Reuse an existing connection, or create a new one if None.
    """
    store = vector_store or get_vector_store()
    documents: list[Document] = []
    ids: list[str] = []

    for month, row in monthly_df.iterrows():
        text = monthly_row_to_text(str(month), row)
        metadata = {
            "month": str(month),
            "total": int(row.get("total", 0)),
            "ingested_at": datetime.utcnow().isoformat(),
            **{col: int(row[col]) for col in row.index if col != "total"},
        }
        documents.append(Document(page_content=text, metadata=metadata))
        ids.append(f"monthly_summary_{month}")  # stable ID → idempotent upsert

    logger.info("Upserting %d monthly summary documents to ChromaDB.", len(documents))
    store.add_documents(documents, ids=ids)
    logger.info("Upsert complete.")


def store_single_month_summary(
    month: str,
    row: pd.Series,
    vector_store: Chroma | None = None,
) -> None:
    """
    Convenience wrapper — upsert a single month's summary.

    Parameters
    ----------
    month : str
        Month string, e.g. '2025-03'.
    row : pd.Series
        One row from ``aggregate_by_month()`` output.
    """
    df = pd.DataFrame([row], index=pd.Index([month], name="month"))
    store_monthly_summary(df, vector_store=vector_store)


# ---------------------------------------------------------------------------
# Retrieval operations
# ---------------------------------------------------------------------------

def retrieve_similar_reports(
    query: str,
    k: int = 3,
    vector_store: Chroma | None = None,
) -> list[Document]:
    """
    Perform a similarity search over stored monthly summaries.

    Parameters
    ----------
    query : str
        Natural-language question or month description.
    k : int
        Number of top results to return (default: 3).
    vector_store : Chroma | None
        Reuse an existing store or create one.

    Returns
    -------
    list[Document]
        Top-k most semantically similar monthly reports, with metadata.
    """
    store = vector_store or get_vector_store()
    logger.info("Similarity search: query=%r, k=%d", query, k)
    results = store.similarity_search(query, k=k)
    logger.info("Retrieved %d documents.", len(results))
    return results


def get_retriever(
    k: int = 3,
    vector_store: Chroma | None = None,
) -> VectorStoreRetriever:
    """
    Return a LangChain-compatible retriever for use as a tool in AgentExecutor.

    Parameters
    ----------
    k : int
        Number of documents to retrieve per query.
    vector_store : Chroma | None
        Reuse an existing store or create one.
    """
    store = vector_store or get_vector_store()
    return store.as_retriever(search_kwargs={"k": k})


# ---------------------------------------------------------------------------
# Utility – format retrieved docs for injection into agent context
# ---------------------------------------------------------------------------

def format_retrieved_docs(docs: list[Document]) -> str:
    """
    Format a list of retrieved Documents into a readable block of text.

    Used to inject historical context into the agent's question.
    """
    if not docs:
        return "No historical monthly reports found in the vector store."

    sections = []
    for i, doc in enumerate(docs, start=1):
        month = doc.metadata.get("month", "Unknown")
        sections.append(f"--- Past Report #{i} ({month}) ---\n{doc.page_content}")
    return "\n\n".join(sections)
