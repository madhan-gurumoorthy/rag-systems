"""
components/document_processor.py
--------------------------------
Document processor for preparing documents for RAG systems.
"""

from __future__ import annotations

import logging
from typing import Optional

from semantic_chunking_engine import SemanticChunkingEngine

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents for RAG systems."""

    def __init__(
        self,
        chunking_engine: Optional[SemanticChunkingEngine] = None,
        chunk_overlap: int = 0,
    ):
        """
        Initialize the document processor.

        Parameters
        ----------
        chunking_engine : SemanticChunkingEngine | None
            Semantic chunking engine. Creates new if None.
        chunk_overlap : int
            Character overlap between chunks.
        """
        self.chunking_engine = chunking_engine or SemanticChunkingEngine()
        self.chunk_overlap = chunk_overlap
        logger.info(f"DocumentProcessor initialized with overlap={chunk_overlap}")

    def process_document(self, text: str, metadata: Optional[dict] = None) -> list[dict]:
        """
        Process a document into chunks with metadata.

        Parameters
        ----------
        text : str
            Document text to process.
        metadata : dict | None
            Optional metadata to attach to chunks.

        Returns
        -------
        list[dict]
            List of chunk dictionaries with 'content' and 'metadata' keys.
        """
        chunks = self.chunking_engine.chunk_text(text, overlap=self.chunk_overlap)

        processed_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata["chunk_index"] = i
            chunk_metadata["chunk_count"] = len(chunks)

            processed_chunks.append({
                "content": chunk,
                "metadata": chunk_metadata,
            })

        logger.info(f"Processed document into {len(processed_chunks)} chunks")
        return processed_chunks

    def process_documents(self, documents: list[str], metadatas: Optional[list[dict]] = None) -> list[dict]:
        """
        Process multiple documents.

        Parameters
        ----------
        documents : list[str]
            List of documents to process.
        metadatas : list[dict] | None
            Optional list of metadata dicts (one per document).

        Returns
        -------
        list[dict]
            List of processed chunks.
        """
        all_chunks = []

        for i, doc in enumerate(documents):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else None
            metadata = metadata or {}
            metadata["document_index"] = i

            chunks = self.process_document(doc, metadata)
            all_chunks.extend(chunks)

        logger.info(f"Processed {len(documents)} documents into {len(all_chunks)} chunks")
        return all_chunks
