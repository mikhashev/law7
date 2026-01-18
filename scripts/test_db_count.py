"""Quick test to check database state."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_db_connection
from sqlalchemy import text

# Check document count
with get_db_connection() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM documents"))
    doc_count = result.scalar()
    print(f"Documents in PostgreSQL: {doc_count}")

    result = conn.execute(text("SELECT COUNT(*) FROM document_content WHERE full_text IS NOT NULL"))
    content_count = result.scalar()
    print(f"Documents with content: {content_count}")

    if doc_count > 0:
        result = conn.execute(text("SELECT eo_number, name, publish_date FROM documents ORDER BY publish_date DESC LIMIT 3"))
        print(f"\nRecent documents:")
        for row in result:
            print(f"  - {row[0]}: {row[1][:50]}... ({row[2]})")

# Check Qdrant
try:
    from qdrant_client import QdrantClient
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections()
    print(f"\nQdrant collections: {[c.name for c in collections.collections]}")

    if collections.collections:
        for col in collections.collections:
            info = client.get_collection(col.name)
            print(f"  - {col.name}: {info.points_count} points")
except Exception as e:
    print(f"\nQdrant error: {e}")

print("\n=== Database State ===")
