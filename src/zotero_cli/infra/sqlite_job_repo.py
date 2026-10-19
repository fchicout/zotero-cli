import json
import logging
import sqlite3
from typing import Any, List, Optional

from zotero_cli.core.interfaces import JobRepository
from zotero_cli.core.models import Job

logger = logging.getLogger(__name__)


class SqliteJobRepository(JobRepository):
    """
    Persistent job queue implementation using SQLite.
    """

    def __init__(self, database_path: str):
        self.database_path = database_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        # Deliberate, not incidental (Issue #150): once a web backend is
        # polling/draining this queue alongside CLI invocations, WAL lets
        # readers (status polls) proceed without blocking on an in-flight
        # writer (a worker popping/completing a job), instead of the default
        # rollback-journal mode's single-writer-blocks-everyone behavior.
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    next_retry_at TEXT,
                    payload TEXT NOT NULL,
                    last_error TEXT,
                    library_id TEXT
                )
            """
                )
                existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
                if "library_id" not in existing_columns:
                    conn.execute("ALTER TABLE jobs ADD COLUMN library_id TEXT")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_task_status ON jobs (task_type, status)"
                )
        finally:
            conn.close()

    def enqueue(self, job: Job) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                INSERT INTO jobs (item_key, task_type, status, attempts, next_retry_at, payload, last_error, library_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                    (
                        job.item_key,
                        job.task_type,
                        job.status,
                        job.attempts,
                        job.next_retry_at,
                        json.dumps(job.payload),
                        job.last_error,
                        job.library_id,
                    ),
                )
                if cursor.lastrowid is None:
                    raise sqlite3.Error("Failed to retrieve last inserted job ID")
                return int(cursor.lastrowid)
        finally:
            conn.close()

    def get_next_pending(self, task_type: str, library_id: Optional[str] = None) -> Optional[Job]:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                query = """
                    SELECT * FROM jobs
                    WHERE task_type = ? AND status IN ('PENDING', 'RETRY')
                    AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'))
                """
                params: List[str] = [task_type]
                if library_id is not None:
                    # NULL library_id = a legacy/unscoped job (enqueued before
                    # scoping existed, or by a caller with no library_id) -
                    # visible to every queue rather than orphaned by the
                    # filter below.
                    query += " AND (library_id = ? OR library_id IS NULL)"
                    params.append(library_id)
                query += " ORDER BY id ASC LIMIT 1"
                row = conn.execute(query, params).fetchone()

                if row:
                    # A legacy (library_id IS NULL) job claimed by a scoped
                    # queue is stamped with that library_id in the same
                    # BEGIN IMMEDIATE transaction (Issue #289) - otherwise
                    # it stays poachable by every other library's queue on
                    # every subsequent retry cycle, not just this claim,
                    # risking cross-tenant job execution against the wrong
                    # library's gateway.
                    if library_id is not None and row["library_id"] is None:
                        conn.execute(
                            "UPDATE jobs SET status = 'PROCESSING', library_id = ? "
                            "WHERE id = ? AND library_id IS NULL",
                            (library_id, row["id"]),
                        )
                    else:
                        conn.execute(
                            "UPDATE jobs SET status = 'PROCESSING' WHERE id = ?", (row["id"],)
                        )
                    job = self._map_row_to_job(row)
                    job.status = "PROCESSING"
                    if library_id is not None and row["library_id"] is None:
                        job.library_id = library_id
                    return job
                return None
        finally:
            conn.close()

    def update_job(self, job: Job) -> bool:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                UPDATE jobs
                SET status = ?, attempts = ?, next_retry_at = ?, payload = ?, last_error = ?
                WHERE id = ?
            """,
                    (
                        job.status,
                        job.attempts,
                        job.next_retry_at,
                        json.dumps(job.payload),
                        job.last_error,
                        job.id,
                    ),
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def get_job(self, job_id: int) -> Optional[Job]:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return self._map_row_to_job(row)
            return None
        finally:
            conn.close()

    def list_jobs(
        self, task_type: Optional[str] = None, library_id: Optional[str] = None, limit: int = 100
    ) -> List[Job]:
        conn = self._get_connection()
        try:
            query = "SELECT * FROM jobs"
            conditions = []
            params: List[Any] = []
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if library_id is not None:
                # See get_next_pending: NULL library_id is a legacy/unscoped
                # job, shown regardless of which library is asking.
                conditions.append("(library_id = ? OR library_id IS NULL)")
                params.append(library_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
            return [self._map_row_to_job(row) for row in cursor]
        finally:
            conn.close()

    def _map_row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            item_key=row["item_key"],
            task_type=row["task_type"],
            status=row["status"],
            attempts=row["attempts"],
            next_retry_at=row["next_retry_at"],
            payload=json.loads(row["payload"]),
            last_error=row["last_error"],
            library_id=row["library_id"],
        )
