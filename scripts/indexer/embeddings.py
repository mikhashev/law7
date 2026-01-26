"""
Embeddings Generator for semantic search.
Uses sentence-transformers to generate embeddings for document text.
Based on ygbis patterns for batch processing and error handling.
"""
import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.core.config import EMBEDDING_BATCH_SIZE, EMBEDDING_DEVICE, EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class EmbeddingsGenerator:
    """
    Generate embeddings for document text using sentence-transformers.

    Supports:
    - Multilingual models for Russian text
    - Batch processing for efficiency
    - Caching to avoid re-computation
    - Chunking for long documents
    """

    # Default chunk size for splitting long documents
    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_CHUNK_OVERLAP = 50

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initialize the embeddings generator.

        Args:
            model_name: Name of the sentence-transformers model
                       (defaults to config EMBEDDING_MODEL)
            device: Device to run on ('cpu' or 'cuda', defaults to config)
            batch_size: Batch size for encoding (defaults to config)
        """
        self.model_name = model_name or EMBEDDING_MODEL
        self.device = device or EMBEDDING_DEVICE
        self.batch_size = batch_size or EMBEDDING_BATCH_SIZE

        logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.vector_size = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Vector size: {self.vector_size}")

        # Cache for embeddings (text hash -> embedding)
        self._cache: Dict[str, np.ndarray] = {}

    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for text caching."""
        if not text:
            return ""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def encode(
        self,
        text: Union[str, List[str]],
        prompt_name: Optional[str] = None,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode text to embeddings.

        Args:
            text: Single text string or list of strings
            prompt_name: Named prompt from sentence-transformers (for USER2-base, etc.)
                       Options: "search_query", "search_document", "classification", "clustering"
            show_progress: Show progress bar for batch processing

        Returns:
            Embeddings as numpy array of shape (n_texts, vector_size)

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> embeddings = generator.encode(["трудовой кодекс", "семейный кодекс"])
            >>> print(embeddings.shape)
            (2, 768)

            For USER2-base with prompts:
            >>> query_emb = generator.encode(["трудовой договор"], prompt_name="search_query")
            >>> doc_emb = generator.encode(["Трудовой кодекс..."], prompt_name="search_document")
        """
        if isinstance(text, str):
            text = [text]

        # Filter out empty strings
        valid_indices = [i for i, t in enumerate(text) if t and t.strip()]
        valid_texts = [text[i] for i in valid_indices]

        if not valid_texts:
            # Return zeros for empty input
            return np.zeros((len(text), self.vector_size), dtype=np.float32)

        # Check cache (note: cache key should include prompt_name)
        embeddings = np.zeros((len(text), self.vector_size), dtype=np.float32)
        cache_hits = []

        for i, (idx, txt) in enumerate(zip(valid_indices, valid_texts)):
            text_hash = self._get_text_hash(txt)
            cache_key = f"{prompt_name}:{text_hash}" if prompt_name else text_hash
            if cache_key in self._cache:
                embeddings[idx] = self._cache[cache_key]
                cache_hits.append(i)

        # Encode non-cached texts
        remaining_texts = [
            txt for i, txt in enumerate(valid_texts)
            if i not in cache_hits
        ]

        if remaining_texts:
            encode_kwargs = {
                "batch_size": self.batch_size,
                "show_progress_bar": show_progress,
                "convert_to_numpy": True,
            }

            # Add prompt_name for models that support it (USER2-base, etc.)
            if prompt_name:
                encode_kwargs["prompt_name"] = prompt_name

            remaining_embeddings = self.model.encode(remaining_texts, **encode_kwargs)
            remaining_embeddings = remaining_embeddings.astype(np.float32)

            # Update cache and results
            j = 0
            for i, (idx, txt) in enumerate(zip(valid_indices, valid_texts)):
                if i not in cache_hits:
                    embeddings[idx] = remaining_embeddings[j]
                    text_hash = self._get_text_hash(txt)
                    cache_key = f"{prompt_name}:{text_hash}" if prompt_name else text_hash
                    self._cache[cache_key] = remaining_embeddings[j]
                    j += 1

        return embeddings

    def encode_documents(
        self,
        documents: List[Dict[str, Any]],
        text_field: str = "full_text",
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode a list of documents to embeddings.

        Args:
            documents: List of document dictionaries
            text_field: Field name containing the text to encode
            show_progress: Show progress bar

        Returns:
            Embeddings as numpy array

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> docs = [
            ...     {"id": "1", "full_text": "трудовой договор"},
            ...     {"id": "2", "full_text": "семейный кодекс"},
            ... ]
            >>> embeddings = generator.encode_documents(docs)
        """
        texts = [doc.get(text_field, "") for doc in documents]
        return self.encode(texts, show_progress=show_progress)

    def chunk_text(
        self,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[str]:
        """
        Split long text into chunks for embedding.

        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of text chunks

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> text = "Article 1. This is the first article. " * 100
            >>> chunks = generator.chunk_text(text, chunk_size=200)
            >>> print(len(chunks))
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0
        min_progress = chunk_size // 4  # Minimum progress per iteration
        no_progress_count = 0
        max_no_progress = 3  # Switch to simple chunking after this many stalls

        while start < len(text):
            end = start + chunk_size
            original_end = end

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending
                for sep in [". ", "! ", "? ", "\n", ".\n", "!\n", "?\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep != -1:
                        end = last_sep + len(sep)
                        break

            # Check if we're making meaningful progress
            if end - start < min_progress:
                no_progress_count += 1
            else:
                no_progress_count = 0

            # If stuck multiple times, switch to simple fixed-size chunking
            if no_progress_count >= max_no_progress:
                # Fall back to simple chunking for the rest of the text
                remaining_start = start
                while remaining_start < len(text):
                    chunk_end = min(remaining_start + chunk_size, len(text))
                    chunk = text[remaining_start:chunk_end].strip()
                    if chunk:
                        chunks.append(chunk)
                    remaining_start = chunk_end - overlap if chunk_end < len(text) else len(text)
                break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap if end < len(text) else len(text)

        return chunks

    def encode_chunks(
        self,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Dict[str, Any]]:
        """
        Chunk text and encode each chunk.

        Args:
            text: Text to chunk and encode
            chunk_size: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of dictionaries with chunk_text, embedding, and position

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> text = "Long legal document text..."
            >>> chunks = generator.encode_chunks(text, chunk_size=500)
            >>> for chunk in chunks:
            ...     print(chunk['chunk_id'], chunk['chunk_text'][:50])
        """
        chunks = self.chunk_text(text, chunk_size, overlap)

        if not chunks:
            return []

        embeddings = self.encode(chunks, show_progress=False)

        results = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Generate a proper UUID for chunk_id (Qdrant requires UUID or unsigned integer)
            chunk_hash = self._get_text_hash(chunk_text)
            chunk_uuid = uuid.uuid5(uuid.NAMESPACE_X500, f"{chunk_hash}_{i}")
            results.append({
                "chunk_id": str(chunk_uuid),
                "chunk_text": chunk_text,
                "chunk_index": i,
                "embedding": embedding.tolist(),
                "embedding_size": self.vector_size,
            })

        return results

    def encode_document_chunks(
        self,
        doc_data: Dict[str, Any],
        text_field: str = "full_text",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document's text and encode each chunk.

        Args:
            doc_data: Document dictionary
            text_field: Field containing the text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of chunk dictionaries with embeddings

        Example:
            >>> generator = EmbeddingsGenerator()
            >>> doc = {"id": "doc1", "full_text": "Long document..."}
            >>> chunks = generator.encode_document_chunks(doc)
        """
        text = doc_data.get(text_field, "")
        doc_id = doc_data.get("id", doc_data.get("eo_number", ""))

        if not text:
            return []

        chunks = self.encode_chunks(text, chunk_size, overlap)

        # Add document metadata to each chunk
        for chunk in chunks:
            chunk["document_id"] = doc_id
            chunk["source_field"] = text_field

        return chunks

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_size(self) -> int:
        """Get the number of items in the cache."""
        return len(self._cache)


# Convenience function for quick usage
def generate_embeddings(
    texts: Union[str, List[str]],
    model_name: Optional[str] = None,
) -> np.ndarray:
    """
    Convenience function to generate embeddings.

    Args:
        texts: Text or list of texts to encode
        model_name: Optional model name override

    Returns:
        Embeddings as numpy array

    Example:
        >>> from indexer.embeddings import generate_embeddings
        >>> embeddings = generate_embeddings(["трудовой кодекс"])
        >>> print(embeddings.shape)
    """
    with EmbeddingsGenerator(model_name=model_name) as generator:
        return generator.encode(texts)


def chunk_and_encode(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> List[Dict[str, Any]]:
    """
    Convenience function to chunk text and encode each chunk.

    Args:
        text: Text to chunk and encode
        chunk_size: Maximum characters per chunk
        overlap: Overlap between chunks

    Returns:
        List of chunk dictionaries with embeddings

    Example:
        >>> from indexer.embeddings import chunk_and_encode
        >>> chunks = chunk_and_encode("Long document text...")
        >>> print(chunks[0]['chunk_text'][:50])
    """
    with EmbeddingsGenerator() as generator:
        return generator.encode_chunks(text, chunk_size, overlap)
