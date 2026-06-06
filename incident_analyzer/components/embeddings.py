"""
components/embeddings.py
------------------------
Embeddings manager for generating and caching document embeddings.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingsManager:
    """Manages embeddings generation and caching."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embeddings manager.

        Parameters
        ----------
        model_name : str
            HuggingFace model name for embeddings.
        """
        self.model = SentenceTransformer(model_name, device="cpu")
        self.model_name = model_name
        self.cache: dict[str, np.ndarray] = {}
        logger.info(f"EmbeddingsManager initialized with {model_name}")

    def embed(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Generate embedding for text.

        Parameters
        ----------
        text : str
            Text to embed.
        use_cache : bool
            Whether to use cached embedding if available.

        Returns
        -------
        np.ndarray
            Embedding vector.
        """
        if use_cache and text in self.cache:
            return self.cache[text]

        embedding = self.model.encode(text, convert_to_numpy=True)

        if use_cache:
            self.cache[text] = embedding

        return embedding

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        Generate embeddings for multiple texts.

        Parameters
        ----------
        texts : list[str]
            List of texts to embed.

        Returns
        -------
        list[np.ndarray]
            List of embedding vectors.
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return list(embeddings) if isinstance(embeddings, np.ndarray) and len(embeddings.shape) > 1 else [embeddings]

    def similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Parameters
        ----------
        text1 : str
            First text.
        text2 : str
            Second text.

        Returns
        -------
        float
            Cosine similarity score (0-1).
        """
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)

        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        return float(dot_product / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0

    def clear_cache(self) -> None:
        """Clear the embeddings cache."""
        self.cache.clear()
        logger.info("Embeddings cache cleared")
