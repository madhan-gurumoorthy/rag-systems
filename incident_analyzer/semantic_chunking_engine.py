"""
semantic_chunking_engine.py
----------------------------
Semantic chunking engine for splitting documents into meaningful chunks
based on semantic similarity rather than fixed sizes.

This module provides intelligent document chunking that preserves context
and meaning, making it ideal for RAG (Retrieval-Augmented Generation) systems.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SemanticChunkingEngine:
    """Chunks documents into semantically coherent segments."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.5,
        min_chunk_size: int = 50,
        max_chunk_size: int = 500,
    ):
        """
        Initialize the chunking engine.

        Parameters
        ----------
        model_name : str
            HuggingFace model name for embeddings.
        similarity_threshold : float
            Cosine similarity threshold for chunk boundaries (0-1).
        min_chunk_size : int
            Minimum characters per chunk.
        max_chunk_size : int
            Maximum characters per chunk.
        """
        self.model = SentenceTransformer(model_name, device="cpu")
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        logger.info(f"SemanticChunkingEngine initialized with {model_name}")

    def chunk_text(self, text: str, overlap: int = 0) -> list[str]:
        """
        Split text into semantically coherent chunks.

        Parameters
        ----------
        text : str
            Text to chunk.
        overlap : int
            Number of characters to overlap between chunks.

        Returns
        -------
        list[str]
            List of semantic chunks.
        """
        sentences = self._split_into_sentences(text)
        if not sentences:
            return [text] if text else []

        chunks = self._group_sentences_into_chunks(sentences)
        return self._apply_overlap(chunks, overlap)

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re

        # Simple sentence splitting on '. ', '! ', '? '
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences_into_chunks(self, sentences: list[str]) -> list[str]:
        """Group sentences into chunks based on semantic similarity."""
        if not sentences:
            return []

        embeddings = self.model.encode(sentences, convert_to_numpy=True)
        chunks = []
        current_chunk_sentences = [sentences[0]]
        current_chunk_embedding = embeddings[0]

        for i in range(1, len(sentences)):
            sentence = sentences[i]
            embedding = embeddings[i]

            similarity = self._cosine_similarity(current_chunk_embedding, embedding)

            current_chunk_text = " ".join(current_chunk_sentences)
            if (
                similarity < self.similarity_threshold
                or len(current_chunk_text) > self.max_chunk_size
            ):
                if len(current_chunk_text) >= self.min_chunk_size:
                    chunks.append(current_chunk_text)
                current_chunk_sentences = [sentence]
                current_chunk_embedding = embedding
            else:
                current_chunk_sentences.append(sentence)
                current_chunk_embedding = (
                    current_chunk_embedding + embedding
                ) / 2  # Update centroid

        # Add final chunk
        final_chunk = " ".join(current_chunk_sentences)
        if final_chunk and len(final_chunk) >= self.min_chunk_size:
            chunks.append(final_chunk)

        logger.info(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")
        return chunks

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

    @staticmethod
    def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
        """Apply character overlap between chunks."""
        if overlap == 0 or len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            overlap_text = prev_chunk[-overlap:] if overlap < len(prev_chunk) else ""
            overlapped_chunks.append(overlap_text + curr_chunk)

        return overlapped_chunks
