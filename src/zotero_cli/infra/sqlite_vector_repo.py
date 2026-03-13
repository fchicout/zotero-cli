import json
import math
import sqlite3
from typing import List

from zotero_cli.core.interfaces import VectorRepository
from zotero_cli.core.models import SearchResult, VectorChunk


class SQLiteVectorRepository(VectorRepository):
    """
    Simple Vector Store using SQLite and Cosine Similarity in Python.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS vector_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL
                )
            """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_item_key ON vector_chunks (item_key)")
        finally:
            conn.close()

    def store_chunks(self, chunks: List[VectorChunk]) -> bool:
        """
        Store multiple vector chunks in the database.
        """
        conn = self._get_connection()
        try:
            with conn:
                for chunk in chunks:
                    embedding_json = json.dumps(chunk.embedding)
                    conn.execute(
                        "INSERT INTO vector_chunks (item_key, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                        (chunk.item_key, chunk.chunk_index, chunk.text, embedding_json),
                    )
            return True
        finally:
            conn.close()

    def search(self, embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """
        Search for semantically similar chunks using Cosine Similarity.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT item_key, text, embedding FROM vector_chunks")
            all_chunks = cursor.fetchall()
        finally:
            conn.close()

        results = []
        for item_key, text, stored_embedding_json in all_chunks:
            try:
                stored_embedding = json.loads(stored_embedding_json)
                score = self._cosine_similarity(embedding, stored_embedding)
                results.append(SearchResult(item_key=item_key, text=text, score=score, metadata={}))
            except (json.JSONDecodeError, TypeError):
                continue

        # Sort by score descending and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def get_chunks_by_item(self, item_key: str) -> List[VectorChunk]:
        """
        Retrieve all chunks for a specific item.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT item_key, chunk_index, text, embedding, id FROM vector_chunks WHERE item_key = ? ORDER BY chunk_index",
                (item_key,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            VectorChunk(
                item_key=row[0],
                chunk_index=row[1],
                text=row[2],
                embedding=json.loads(row[3]),
                id=row[4],
            )
            for row in rows
        ]

    def delete_chunks_by_item(self, item_key: str) -> bool:
        """
        Delete all chunks associated with an item.
        """
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM vector_chunks WHERE item_key = ?", (item_key,))
            return True
        finally:
            conn.close()

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """
        Calculates Cosine Similarity between two vectors.
        """
        if len(v1) != len(v2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(a * a for a in v2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)
