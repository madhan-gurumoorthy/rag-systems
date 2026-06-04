"""
milvus_store.py
---------------
Milvus vector-store integration for monthly incident summary reports.

Responsibilities
----------------
1. Connect to a Milvus instance (standalone or cloud) using env vars.
2. Serialise a monthly pivot-table row into a text document and upsert it.
3. Expose a retriever that does similarity search over stored reports —
   used by the AgentExecutor tool in agent.py.

Environment Variables
---------------------
MILVUS_URI          URI of Milvus (e.g. "http://localhost:19530" or a Zilliz Cloud URI)
MILVUS_TOKEN        (optional) API token for Zilliz Cloud; empty string for local
MILVUS_COLLECTION   Collection name (default: "incident_monthly_summaries")
OPENAI_API_KEY      Required for OpenAI embeddings (see EMBEDDINGS note below)

EMBEDDINGS NOTE
---------------
We default to OpenAI's text-embedding-3-small because it is a strong, widely
available default.  To swap providers, replace the `_build_embeddings()` function:

    # HuggingFace (no API key needed):
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

    # Azure OpenAI:
    from langchain_openai import AzureOpenAIEmbeddings
    return AzureOpenAIEmbeddings(azure_deployment="text-embedding-ada-002", ...)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import pandas as pd
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_milvus import Milvus
from langchain_openai import OpenAIEmbeddings

from incident_processor import monthly_row_to_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------

_DEFAULT_COLLECTION = "incident_monthly_summaries"


def _get_config() -> dict[str, Any]:
    return {
        "uri": os.environ.get("MILVUS_URI", "http://localhost:19530"),
        "token": os.environ.get("MILVUS_TOKEN", ""),
        "collection": os.environ.get("MILVUS_COLLECTION", _DEFAULT_COLLECTION),
    }


# ---------------------------------------------------------------------------
# Embeddings factory (swap here to change provider)
# ---------------------------------------------------------------------------

def _build_embeddings() -> OpenAIEmbeddings:
    """
    Build the embeddings model.

    Default: OpenAI text-embedding-3-small.
    Requires OPENAI_API_KEY in the environment.
    See module docstring for alternative providers.
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        # api_key is picked up automatically from OPENAI_API_KEY env var
    )


# ---------------------------------------------------------------------------
# Vector store factory
# ---------------------------------------------------------------------------

def get_vector_store() -> Milvus:
    """
    Return a connected Milvus vector store instance.

    The collection is created automatically on first use.
    `auto_id=True` lets Milvus generate primary keys — avoids duplicate-key
    errors when upserting new documents.
    """
    cfg = _get_config()
    embeddings = _build_embeddings()

    logger.info(
        "Connecting to Milvus at %s, collection='%s'",
        cfg["uri"],
        cfg["collection"],
    )

    store = Milvus(
        embedding_function=embeddings,
        collection_name=cfg["collection"],
        connection_args={
            "uri": cfg["uri"],
            **({"token": cfg["token"]} if cfg["token"] else {}),
        },
        auto_id=True,
        drop_old=False,   # keep existing data between runs
    )
    return store


# ---------------------------------------------------------------------------
# Store operations
# ---------------------------------------------------------------------------

def store_monthly_summary(
    monthly_df: pd.DataFrame,
    vector_store: Milvus | None = None,
) -> None:
    """
    Upsert all rows from the monthly pivot table into Milvus.

    Each row becomes one Document whose:
      - page_content = human-readable summary text (embedded for similarity search)
      - metadata     = {month, ingested_at, per-category counts}

    Parameters
    ----------
    monthly_df : pd.DataFrame
        Output of ``aggregate_by_month()`` — index is 'month' (YYYY-MM strings).
    vector_store : Milvus | None
        Reuse an existing connection, or create a new one if None.
    """
    store = vector_store or get_vector_store()
    documents: list[Document] = []

    for month, row in monthly_df.iterrows():
        text = monthly_row_to_text(str(month), row)
        metadata = {
            "month": str(month),
            "total": int(row.get("total", 0)),
            "ingested_at": datetime.utcnow().isoformat(),
            **{col: int(row[col]) for col in row.index if col != "total"},
        }
        documents.append(Document(page_content=text, metadata=metadata))

    logger.info("Upserting %d monthly summary documents to Milvus.", len(documents))
    store.add_documents(documents)
    logger.info("Upsert complete.")


def store_single_month_summary(
    month: str,
    row: pd.Series,
    vector_store: Milvus | None = None,
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
    vector_store: Milvus | None = None,
) -> list[Document]:
    """
    Perform a similarity search over stored monthly summaries.

    Parameters
    ----------
    query : str
        Natural-language question or month description, e.g.
        "incidents in March 2025" or "trend last month".
    k : int
        Number of top results to return (default: 3).
    vector_store : Milvus | None
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
    vector_store: Milvus | None = None,
) -> VectorStoreRetriever:
    """
    Return a LangChain-compatible retriever for use as a tool in AgentExecutor.

    Parameters
    ----------
    k : int
        Number of documents to retrieve per query.
    vector_store : Milvus | None
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
