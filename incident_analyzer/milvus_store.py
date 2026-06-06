"""
milvus_store.py
---------------
Milvus vector-store integration for incident monthly summaries.

Use as alternative to chroma_store.py for production deployments.
Run Milvus: docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections

from incident_processor import monthly_row_to_text
from components.embeddings import EmbeddingsManager

logger = logging.getLogger(__name__)

_DEFAULT_MILVUS_HOST = "localhost"
_DEFAULT_MILVUS_PORT = 19530
_DEFAULT_COLLECTION_NAME = "incident_monthly_summaries"


def _get_config() -> dict:
    return {
        "host": os.environ.get("MILVUS_HOST", _DEFAULT_MILVUS_HOST),
        "port": int(os.environ.get("MILVUS_PORT", _DEFAULT_MILVUS_PORT)),
        "collection": os.environ.get("MILVUS_COLLECTION", _DEFAULT_COLLECTION_NAME),
    }


def _connect_to_milvus(host: str, port: int) -> None:
    """Connect to Milvus server."""
    try:
        connections.connect("default", host=host, port=port)
        logger.info(f"Connected to Milvus at {host}:{port}")
    except Exception as e:
        logger.error(f"Failed to connect to Milvus: {e}")
        raise


def _create_collection_schema() -> CollectionSchema:
    """Create schema for incident summary collection."""
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=384),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=5000),
        FieldSchema(name="month", dtype=DataType.VARCHAR, max_length=20),
        FieldSchema(name="timestamp", dtype=DataType.INT64),
    ]
    return CollectionSchema(fields=fields, description="Monthly incident summaries")


def _get_or_create_collection(collection_name: str) -> Collection:
    """Get existing collection or create new one."""
    try:
        collection = Collection(collection_name)
        logger.info(f"Using existing collection: {collection_name}")
        return collection
    except Exception:
        logger.info(f"Creating new collection: {collection_name}")
        schema = _create_collection_schema()
        collection = Collection(name=collection_name, schema=schema, using="default")
        collection.create_index(
            field_name="vector",
            index_params={
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 200},
            }
        )
        logger.info(f"Created index for collection: {collection_name}")
        return collection


def get_vector_store() -> Collection:
    """Return Milvus collection instance."""
    cfg = _get_config()
    _connect_to_milvus(cfg["host"], cfg["port"])
    collection = _get_or_create_collection(cfg["collection"])
    logger.info(f"Milvus store ready: {cfg['host']}:{cfg['port']}")
    return collection


def store_monthly_summary(
    monthly_df: pd.DataFrame,
    collection: Collection | None = None,
    embeddings_manager: Optional[EmbeddingsManager] = None,
) -> None:
    """Upsert monthly summaries into Milvus."""
    col = collection or get_vector_store()
    emb_mgr = embeddings_manager or EmbeddingsManager()

    ids, vectors, texts, months, timestamps = [], [], [], [], []
    timestamp_now = int(datetime.utcnow().timestamp())

    for month, row in monthly_df.iterrows():
        month_str = str(month)
        text = monthly_row_to_text(month_str, row)
        embedding = emb_mgr.embed(text)

        ids.append(f"monthly_summary_{month_str}")
        vectors.append(embedding.tolist())
        texts.append(text)
        months.append(month_str)
        timestamps.append(timestamp_now)

    col.insert([ids, vectors, texts, months, timestamps])
    col.flush()
    logger.info(f"Upserted {len(ids)} summaries to Milvus")


def retrieve_similar_reports(
    query: str,
    k: int = 3,
    collection: Collection | None = None,
    embeddings_manager: Optional[EmbeddingsManager] = None,
) -> list[tuple[str, float]]:
    """Similarity search in Milvus."""
    col = collection or get_vector_store()
    emb_mgr = embeddings_manager or EmbeddingsManager()

    query_embedding = emb_mgr.embed(query)
    logger.info(f"Searching for similar reports: {query!r}, k={k}")

    search_params = {"metric_type": "COSINE", "params": {"ef": 32}}
    results = col.search(
        data=[query_embedding.tolist()],
        anns_field="vector",
        param=search_params,
        limit=k,
        output_fields=["text", "month"],
    )

    retrieved = []
    if results and len(results) > 0:
        for hit in results[0]:
            text = hit.get("text", "")
            distance = hit.distance
            similarity = 1 - (distance / 2)
            retrieved.append((text, float(similarity)))

    logger.info(f"Retrieved {len(retrieved)} documents")
    return retrieved
