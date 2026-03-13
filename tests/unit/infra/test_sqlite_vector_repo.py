import os
import sqlite3
from contextlib import closing

import pytest

from zotero_cli.core.models import VectorChunk
from zotero_cli.infra.sqlite_vector_repo import SQLiteVectorRepository


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_vector.db"
    return str(db_path)

@pytest.mark.unit
def test_sqlite_vector_repo_init(temp_db):
    SQLiteVectorRepository(temp_db)
    assert os.path.exists(temp_db)

    with closing(sqlite3.connect(temp_db)) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vector_chunks'"
        )
        assert cursor.fetchone() is not None

@pytest.mark.unit
def test_sqlite_vector_repo_store_and_get(temp_db):
    repo = SQLiteVectorRepository(temp_db)
    chunks = [
        VectorChunk(item_key="KEY1", chunk_index=0, text="chunk1", embedding=[0.1, 0.2]),
        VectorChunk(item_key="KEY1", chunk_index=1, text="chunk2", embedding=[0.3, 0.4]),
    ]
    repo.store_chunks(chunks)

    retrieved = repo.get_chunks_by_item("KEY1")
    assert len(retrieved) == 2
    assert retrieved[0].text == "chunk1"
    assert retrieved[1].embedding == [0.3, 0.4]

@pytest.mark.unit
def test_sqlite_vector_repo_search(temp_db):
    repo = SQLiteVectorRepository(temp_db)
    chunks = [
        VectorChunk(item_key="KEY1", chunk_index=0, text="exact match", embedding=[1.0, 0.0]),
        VectorChunk(item_key="KEY2", chunk_index=0, text="no match", embedding=[0.0, 1.0]),
    ]
    repo.store_chunks(chunks)

    results = repo.search([1.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0].item_key == "KEY1"
    assert results[0].score > 0.99

    results_none = repo.search([0.0, 1.0], top_k=1)
    assert results_none[0].item_key == "KEY2"
