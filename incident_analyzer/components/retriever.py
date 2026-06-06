"""
components/retriever.py
-----------------------
Semantic retriever for similarity-based document retrieval.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from .embeddings import EmbeddingsManager

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """Retrieves semantically similar documents from a collection."""

    def __init__(self, embeddings_manager: Optional[EmbeddingsManager] = None):
        """
        Initialize the retriever.

        Parameters
        ----------
        embeddings_manager : EmbeddingsManager | None
            Embeddings manager instance. Creates new if None.
        """
        self.embeddings_manager = embeddings_manager or EmbeddingsManager()
        self.documents: list[str] = []
        self.embeddings: list[np.ndarray] = []
        logger.info("SemanticRetriever initialized")

    def add_documents(self, documents: list[str]) -> None:
        """
        Add documents to the retriever.

        Parameters
        ----------
        documents : list[str]
            List of documents to add.
        """
        self.documents.extend(documents)
        new_embeddings = self.embeddings_manager.embed_batch(documents)
        self.embeddings.extend(new_embeddings)
        logger.info(f"Added {len(documents)} documents. Total: {len(self.documents)}")

    def retrieve(self, query: str, k: int = 3, threshold: float = 0.0) -> list[tuple[str, float]]:
        """
        Retrieve top-k most similar documents.

        Parameters
        ----------
        query : str
            Query text.
        k : int
            Number of documents to retrieve.
        threshold : float
            Minimum similarity score.

        Returns
        -------
        list[tuple[str, float]]
            List of (document, similarity_score) tuples.
        """
        if not self.documents:
            logger.warning("No documents in retriever")
            return []

        query_embedding = self.embeddings_manager.embed(query)

        similarities = []
        for doc, doc_embedding in zip(self.documents, self.embeddings):
            similarity = self._cosine_similarity(query_embedding, doc_embedding)
            if similarity >= threshold:
                similarities.append((doc, similarity))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        results = similarities[:k]
        logger.info(f"Retrieved {len(results)} documents for query (top-{k})")
        return results

    def clear(self) -> None:
        """Clear all documents and embeddings."""
        self.documents.clear()
        self.embeddings.clear()
        logger.info("Retriever cleared")

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return float(dot_product / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
