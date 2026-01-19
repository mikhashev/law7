"""
Content and Embeddings Sync Script for law7.
Extracts document content and generates embeddings for semantic search.
Based on ygbis patterns for batch processing and progress tracking.
"""
import gc
import logging
import os
import psutil
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import EMBEDDING_BATCH_SIZE, SYNC_BATCH_SIZE
from core.db import get_db_connection
from indexer.embeddings import EmbeddingsGenerator
from sqlalchemy import text
from indexer.qdrant_indexer import QdrantIndexer
from parser.html_parser import PravoContentParser
from utils.progress import ProgressTracker
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def log_memory(message: str):
    """Log current memory usage."""
    mem_mb = get_memory_usage_mb()
    logger.info(f"[MEMORY] {message}: {mem_mb:.1f} MB")


class ContentSyncService:
    """
    Service for syncing document content and generating embeddings.
    1. Fetches documents from PostgreSQL
    2. Parses content from API metadata
    3. Generates embeddings
    4. Stores in Qdrant
    """

    def __init__(
        self,
        batch_size: int = SYNC_BATCH_SIZE,
        embedding_batch_size: int = EMBEDDING_BATCH_SIZE,
        skip_embeddings: bool = False,
    ):
        """Initialize the content sync service."""
        self.batch_size = batch_size
        self.embedding_batch_size = embedding_batch_size
        self.skip_embeddings = skip_embeddings

        self.content_parser = PravoContentParser()
        log_memory("Before loading model")
        self.embeddings_generator = None if skip_embeddings else EmbeddingsGenerator()
        log_memory("After loading model")
        self.qdrant_indexer = None if skip_embeddings else QdrantIndexer()
        self.progress = ProgressTracker()

    def _fetch_documents(
        self,
        limit: int = None,
        country_id: int = 1,
    ) -> list:
        """Fetch documents from PostgreSQL."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        query = f"""
            SELECT
                d.id,
                d.eo_number,
                d.title,
                d.name,
                d.complex_name,
                d.document_number,
                d.document_date,
                d.publish_date,
                d.pages_count,
                d.signatory_authority_id,
                d.document_type_id,
                d.publication_block_id,
                d.country_id,
                dc.full_text as existing_full_text,
                dc.text_hash as existing_text_hash
            FROM documents d
            LEFT JOIN document_content dc ON d.id = dc.document_id
            WHERE d.country_id = {country_id}
            ORDER BY d.publish_date DESC
            {limit_clause}
        """

        with get_db_connection() as conn:
            result = conn.execute(text(query))
            columns = result.keys()
            results = result.fetchall()

        return [dict(zip(columns, row)) for row in results]

    def _upsert_content(
        self,
        document_id: str,
        content: dict,
    ):
        """Upsert document content to PostgreSQL."""
        query = text("""
            INSERT INTO document_content (document_id, full_text, raw_text, pdf_url, html_url, text_hash)
            VALUES (:document_id, :full_text, :raw_text, :pdf_url, :html_url, :text_hash)
            ON CONFLICT (document_id) DO UPDATE
            SET
                full_text = EXCLUDED.full_text,
                raw_text = EXCLUDED.raw_text,
                pdf_url = EXCLUDED.pdf_url,
                html_url = EXCLUDED.html_url,
                text_hash = EXCLUDED.text_hash,
                updated_at = NOW()
        """)

        with get_db_connection() as conn:
            conn.execute(query, {
                "document_id": document_id,
                "full_text": content.get("full_text"),
                "raw_text": content.get("raw_text"),
                "pdf_url": content.get("pdf_url"),
                "html_url": content.get("html_url"),
                "text_hash": content.get("text_hash"),
            })
            conn.commit()

    def run(
        self,
        limit: int = None,
        skip_content: bool = False,
        skip_embeddings: bool = False,
        recreate_collection: bool = False,
    ) -> dict:
        """
        Run the content sync process.

        Args:
            limit: Limit number of documents to process (for testing)
            skip_content: Skip content parsing (use existing)
            skip_embeddings: Skip embedding generation
            recreate_collection: Recreate Qdrant collection

        Returns:
            Dictionary with sync statistics
        """
        logger.info("="*60)
        logger.info("Law7 Content & Embeddings Sync Service")
        logger.info("="*60)
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Embedding batch size: {self.embedding_batch_size}")
        logger.info(f"Limit: {limit or 'No limit'}")
        logger.info(f"Skip content: {skip_content}")
        logger.info(f"Skip embeddings: {skip_embeddings}")
        logger.info(f"Recreate collection: {recreate_collection}")
        logger.info("="*60)

        start_time = datetime.now()

        # Setup Qdrant collection
        if not skip_embeddings:
            if recreate_collection:
                logger.info("Recreating Qdrant collection...")
                self.qdrant_indexer.create_collection(recreate=True)
            else:
                self.qdrant_indexer.create_collection(recreate=False)

        # Fetch documents
        logger.info("Fetching documents from PostgreSQL...")
        documents = self._fetch_documents(limit=limit)
        logger.info(f"Found {len(documents)} documents")
        log_memory("After loading documents")

        if not documents:
            logger.warning("No documents found!")
            return {
                "total_documents": 0,
                "content_parsed": 0,
                "embeddings_generated": 0,
                "duration_seconds": 0,
            }

        # Process documents
        content_parsed = 0
        embeddings_generated = 0
        all_chunks = []
        total_docs = len(documents)

        for i, doc in enumerate(tqdm(documents, desc="Processing documents")):
            doc_id = doc["id"]
            doc_type = doc.get("document_type_id")
            title = doc.get("complex_name", doc.get("title", "Unknown"))[:50]  # Truncate for logging
            full_text_len = len(doc.get("existing_full_text") or "")

            # Log document info (first 5 and every 10 after)
            if i < 5 or i % 10 == 0:
                logger.info(f"[DOC {i+1}/{total_docs}] {title}...] ({full_text_len:,} chars, type: {doc_type})")

            # Log memory every 50 documents
            if i % 50 == 0:
                log_memory(f"After {i} documents")

            doc_data = {
                "eoNumber": doc["eo_number"],
                "title": doc["title"],
                "name": doc["name"],
                "complex_name": doc["complex_name"],
            }

            # Parse content (if not skipped)
            if not skip_content:
                content = self.content_parser.parse_document(doc_data)
                if content and content.get("full_text"):
                    self._upsert_content(doc_id, content)
                    content_parsed += 1
                    doc["full_text"] = content["full_text"]
                elif doc.get("existing_full_text"):
                    doc["full_text"] = doc["existing_full_text"]
            else:
                doc["full_text"] = doc.get("existing_full_text") or ""

            # Generate embeddings
            if not skip_embeddings and doc.get("full_text"):
                # Skip extremely long documents that cause performance issues
                text_len = len(doc.get("full_text", ""))
                if text_len > 100000:  # Skip documents over 100KB
                    title = doc.get("complex_name", doc.get("title", "Unknown"))[:50]
                    logger.warning(f"[SKIPPED] {title}... ({text_len:,} chars, type: {doc.get('document_type_id')})")
                    embeddings_generated += 0
                    continue

                chunks = self.embeddings_generator.encode_document_chunks(
                    {**doc, "id": doc_id},
                    text_field="full_text",
                )
                all_chunks.extend(chunks)
                embeddings_generated += len(chunks)
                # Clear cache after each document to prevent memory buildup
                self.embeddings_generator.clear_cache()
                # Force garbage collection and GPU cache clearing
                import gc as gc_module
                gc_module.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

                # Upsert in batches with memory cleanup
                if len(all_chunks) >= self.batch_size:
                    self.qdrant_indexer.upsert_embeddings(all_chunks)
                    all_chunks = []
                    # Extra memory cleanup
                    gc_module.collect()
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
                    log_memory(f"After batch upsert (chunks: {embeddings_generated})")
                    logger.info(f"Batch complete. Total chunks: {embeddings_generated}")

        # Final batch
        if all_chunks and not skip_embeddings:
            self.qdrant_indexer.upsert_embeddings(all_chunks)
            self.embeddings_generator.clear_cache()
            import gc
            gc.collect()

        duration = (datetime.now() - start_time).total_seconds()

        logger.info("="*60)
        logger.info("Sync Complete!")
        logger.info(f"Total documents: {len(documents)}")
        logger.info(f"Content parsed: {content_parsed}")
        logger.info(f"Embeddings generated: {embeddings_generated} chunks")
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info("="*60)

        return {
            "total_documents": len(documents),
            "content_parsed": content_parsed,
            "embeddings_generated": embeddings_generated,
            "duration_seconds": duration,
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync document content and embeddings")
    parser.add_argument("--limit", type=int, help="Limit number of documents (for testing)")
    parser.add_argument("--skip-content", action="store_true", help="Skip content parsing")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")
    parser.add_argument("--recreate-collection", action="store_true", help="Recreate Qdrant collection")
    args = parser.parse_args()

    service = ContentSyncService(skip_embeddings=args.skip_embeddings)
    stats = service.run(
        limit=args.limit,
        skip_content=args.skip_content,
        skip_embeddings=args.skip_embeddings,
        recreate_collection=args.recreate_collection,
    )

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Documents processed: {stats['total_documents']}")
    print(f"Content parsed: {stats['content_parsed']}")
    print(f"Embeddings generated: {stats['embeddings_generated']}")
    print(f"Duration: {stats['duration_seconds']:.1f}s")
    if stats['duration_seconds'] > 0:
        print(f"Rate: {stats['total_documents'] / stats['duration_seconds']:.1f} docs/sec")
    print("="*60)


if __name__ == "__main__":
    main()
