"""
Unified memory configuration for AI-Team.

Provides short-term (ChromaDB), long-term (SQLite), and entity memory stores
with a single MemoryManager interface. Short-term memory is per-project for RAG;
long-term stores conversation history, performance metrics, and learned patterns
across projects; entity memory tracks project structure (files, APIs, services)
and relationships.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import structlog

from ai_team.config.settings import MemorySettings

logger = structlog.get_logger(__name__)

MemoryType = Literal["short_term", "long_term", "entity"]


# -----------------------------------------------------------------------------
# Ollama embedding function for ChromaDB
# -----------------------------------------------------------------------------


class OllamaChromaEmbeddingFunction:
    """
    Embedding function that calls Ollama's embedding API for ChromaDB.
    Implements the interface expected by ChromaDB (Documents -> Embeddings).
    """

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def name(self) -> str:
        """ChromaDB embedding function identifier."""
        return "ollama"

    def is_legacy(self) -> bool:
        """ChromaDB: not a legacy embedding function."""
        return False

    def embed_query(self, input: str | List[str]) -> List[float] | List[List[float]]:
        """ChromaDB query path: embed one or more query strings."""
        if isinstance(input, str):
            vectors = self([input])
            return vectors[0] if vectors else []
        return self(input)

    def __call__(self, input: List[str]) -> List[List[float]]:
        """Embed a list of documents. Returns list of embedding vectors."""
        import httpx

        if not input:
            return []
        out: List[List[float]] = []
        for doc in input:
            try:
                with httpx.Client(timeout=60.0) as client:
                    r = client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.model, "prompt": doc},
                    )
                    r.raise_for_status()
                    data = r.json()
                    out.append(data.get("embedding", []))
            except Exception as e:
                logger.warning("ollama_embedding_failed", doc_len=len(doc), error=str(e))
                # Fallback: zero vector of typical nomic size (768) so ChromaDB doesn't fail
                out.append([0.0] * 768)
        return out


# -----------------------------------------------------------------------------
# Short-term store (ChromaDB) — per-project collection, task outputs as RAG
# -----------------------------------------------------------------------------


class ShortTermStore:
    """
    ChromaDB-backed store for task outputs. One collection per project_id.
    Agents can search previous task results via semantic search.
    """

    def __init__(
        self,
        chromadb_path: str,
        embedding_model: str,
        collection_name: str,
        ollama_base_url: str,
    ) -> None:
        self._chromadb_path = Path(chromadb_path)
        self._chromadb_path.mkdir(parents=True, exist_ok=True)
        self._embedding_model = embedding_model
        self._collection_name_prefix = collection_name
        self._ollama_base_url = ollama_base_url
        self._client: Any = None
        self._ef: Optional[OllamaChromaEmbeddingFunction] = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self._chromadb_path))
            self._ef = OllamaChromaEmbeddingFunction(
                model=self._embedding_model,
                base_url=self._ollama_base_url,
            )
        return self._client

    def _collection_name(self, project_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id)
        return f"{self._collection_name_prefix}_{safe}"

    def get_collection(self, project_id: str):  # noqa: ANN201
        """Get or create the ChromaDB collection for this project."""
        client = self._ensure_client()
        name = self._collection_name(project_id)
        return client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
            metadata={"project_id": project_id},
        )

    def add(
        self,
        project_id: str,
        doc_id: str,
        document: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a task output (or any text) for RAG retrieval."""
        if not document:
            return
        coll = self.get_collection(project_id)
        meta = dict(metadata or {})
        meta["project_id"] = project_id
        coll.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[meta],
        )
        logger.debug("short_term_stored", project_id=project_id, doc_id=doc_id)

    def search(
        self,
        project_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[str, str, float, Dict[str, Any]]]:
        """Search task outputs by semantic similarity. Returns (id, document, distance, metadata)."""
        coll = self.get_collection(project_id)
        result = coll.query(
            query_texts=[query],
            n_results=min(top_k, 100),
            include=["documents", "metadatas", "distances"],
        )
        if not result or not result["ids"] or not result["ids"][0]:
            return []
        ids = result["ids"][0]
        docs = result["documents"][0]
        dists = result.get("distances", [[0.0] * len(ids)])[0]
        metadatas = result.get("metadatas", [[{}] * len(ids)])[0]
        return list(zip(ids, docs, dists, metadatas))

    def delete_collection(self, project_id: str) -> None:
        """Remove project's short-term memory (auto-cleanup after completion)."""
        client = self._ensure_client()
        name = self._collection_name(project_id)
        try:
            client.delete_collection(name=name)
            logger.info("short_term_cleanup", project_id=project_id)
        except Exception as e:
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                logger.debug("short_term_cleanup_skip", project_id=project_id, reason="no_collection")
            else:
                logger.warning("short_term_cleanup_failed", project_id=project_id, error=str(e))


# -----------------------------------------------------------------------------
# Long-term store (SQLite) — conversations, metrics, patterns across projects
# -----------------------------------------------------------------------------

# Shared in-memory connection so LongTermStore and EntityStore use the same DB
_shared_memory_conn: Optional[sqlite3.Connection] = None


def _get_sqlite_connection(path: str) -> sqlite3.Connection:
    """Return a connection. For :memory:, reuse one shared connection so both stores see same DB."""
    global _shared_memory_conn
    if path == ":memory:":
        if _shared_memory_conn is None:
            _shared_memory_conn = sqlite3.connect(":memory:")
        return _shared_memory_conn
    return sqlite3.connect(path)


def _sqlite_path_for_schema(path: str) -> str:
    """Path/uri for schema and connection. :memory: stays as-is for shared conn."""
    if path != ":memory:" and not path.startswith("file:"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


class LongTermStore:
    """
    SQLite-backed store for conversation history, agent performance metrics,
    and learned patterns. Retention applied by created_at and retention_days.
    """

    def __init__(self, sqlite_path: str, retention_days: int) -> None:
        self._path = sqlite_path
        _sqlite_path_for_schema(sqlite_path)
        self._retention_days = retention_days
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return _get_sqlite_connection(self._path)

    @contextmanager
    def _with_conn(self) -> Any:
        conn = self._conn()
        try:
            yield conn
        finally:
            if self._path != ":memory:":
                conn.close()

    def _init_schema(self) -> None:
        with self._with_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_role TEXT NOT NULL,
                model TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_id);
            CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_metrics_created ON performance_metrics(created_at);
            CREATE INDEX IF NOT EXISTS idx_patterns_created ON learned_patterns(created_at);
        """)

    def add_conversation(
        self,
        role: str,
        content: str,
        project_id: Optional[str] = None,
    ) -> str:
        """Append a conversation turn. Returns row id."""
        row_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO conversations (id, project_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (row_id, project_id or "", role, content, now),
            )
        return row_id

    def add_metric(self, agent_role: str, model: str, metric_name: str, value: float) -> None:
        """Record an agent performance metric."""
        now = datetime.utcnow().isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO performance_metrics (agent_role, model, metric_name, value, created_at) VALUES (?, ?, ?, ?, ?)",
                (agent_role, model, metric_name, value, now),
            )

    def add_pattern(self, pattern_type: str, content: str) -> str:
        """Store a learned pattern (e.g. architecture decision, code pattern). Returns id."""
        row_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._with_conn() as conn:
            conn.execute(
                "INSERT INTO learned_patterns (id, pattern_type, content, created_at) VALUES (?, ?, ?, ?)",
                (row_id, pattern_type, content, now),
            )
        return row_id

    def get_recent_conversations(
        self,
        limit: int = 50,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent conversation turns, optionally filtered by project."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if project_id:
                cur = conn.execute(
                    "SELECT id, project_id, role, content, created_at FROM conversations WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT id, project_id, role, content, created_at FROM conversations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_metrics_summary(self) -> List[Dict[str, Any]]:
        """Aggregate performance metrics by role/model for tuning."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT agent_role, model, metric_name, AVG(value) as avg_value, COUNT(*) as count
                FROM performance_metrics
                GROUP BY agent_role, model, metric_name
            """)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_patterns(self, pattern_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve learned patterns, optionally by type."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if pattern_type:
                cur = conn.execute(
                    "SELECT id, pattern_type, content, created_at FROM learned_patterns WHERE pattern_type = ? ORDER BY created_at DESC LIMIT ?",
                    (pattern_type, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT id, pattern_type, content, created_at FROM learned_patterns ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def apply_retention(self) -> int:
        """Delete entries older than retention_days. Returns number of rows deleted."""
        cutoff = (datetime.utcnow() - timedelta(days=self._retention_days)).isoformat()
        deleted = 0
        with self._with_conn() as conn:
            for table in ("conversations", "performance_metrics", "learned_patterns"):
                cur = conn.execute(f"DELETE FROM {table} WHERE created_at < ?", (cutoff,))
                deleted += cur.rowcount
        if deleted:
            logger.info("long_term_retention_applied", deleted=deleted, cutoff=cutoff)
        return deleted


# -----------------------------------------------------------------------------
# Entity store — project entities and relationships
# -----------------------------------------------------------------------------


class EntityStore:
    """
    Tracks project entities (files, APIs, databases, services) and relationships.
    Used by agents to understand project structure; auto-populated from task outputs.
    """

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path
        _sqlite_path_for_schema(sqlite_path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return _get_sqlite_connection(self._path)

    @contextmanager
    def _with_conn(self) -> Any:
        conn = self._conn()
        try:
            yield conn
        finally:
            if self._path != ":memory:":
                conn.close()

    def _init_schema(self) -> None:
        with self._with_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    attributes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, name)
                );
                CREATE TABLE IF NOT EXISTS entity_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    from_entity_id INTEGER NOT NULL,
                    to_entity_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (from_entity_id) REFERENCES entities(id),
                    FOREIGN KEY (to_entity_id) REFERENCES entities(id)
                );
                CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id);
                CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(project_id, name);
                CREATE INDEX IF NOT EXISTS idx_rel_project ON entity_relationships(project_id);
            """)

    def upsert_entity(
        self,
        project_id: str,
        name: str,
        entity_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert or update an entity. Returns entity id."""
        now = datetime.utcnow().isoformat()
        attrs_json = json.dumps(attributes or {})
        with self._with_conn() as conn:
            conn.execute(
                """
                INSERT INTO entities (project_id, name, entity_type, attributes, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, name) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    attributes = excluded.attributes
                """,
                (project_id, name, entity_type, attrs_json, now),
            )
            row = conn.execute(
                "SELECT id FROM entities WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
        return row[0] if row else 0

    def add_relationship(
        self,
        project_id: str,
        from_entity_name: str,
        to_entity_name: str,
        relationship_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a relationship between two entities by name."""
        with self._with_conn() as conn:
            from_id = conn.execute(
                "SELECT id FROM entities WHERE project_id = ? AND name = ?",
                (project_id, from_entity_name),
            ).fetchone()
            to_id = conn.execute(
                "SELECT id FROM entities WHERE project_id = ? AND name = ?",
                (project_id, to_entity_name),
            ).fetchone()
            if not from_id or not to_id:
                logger.debug(
                    "entity_relationship_skipped",
                    project_id=project_id,
                    from_=from_entity_name,
                    to=to_entity_name,
                    reason="entity_not_found",
                )
                return
            now = datetime.utcnow().isoformat()
            meta_json = json.dumps(metadata or {})
            conn.execute(
                """INSERT INTO entity_relationships (project_id, from_entity_id, to_entity_id, relationship_type, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, from_id[0], to_id[0], relationship_type, meta_json, now),
            )

    def get_entity(
        self,
        project_id: str,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """Look up a single entity by project and name."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, project_id, name, entity_type, attributes, created_at FROM entities WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("attributes"):
            try:
                d["attributes"] = json.loads(d["attributes"])
            except (TypeError, json.JSONDecodeError):
                pass
        return d

    def get_entities(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List entities for a project, optionally filtered by type."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            if entity_type:
                cur = conn.execute(
                    "SELECT id, project_id, name, entity_type, attributes, created_at FROM entities WHERE project_id = ? AND entity_type = ?",
                    (project_id, entity_type),
                )
            else:
                cur = conn.execute(
                    "SELECT id, project_id, name, entity_type, attributes, created_at FROM entities WHERE project_id = ?",
                    (project_id,),
                )
            rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("attributes"):
                try:
                    d["attributes"] = json.loads(d["attributes"])
                except (TypeError, json.JSONDecodeError):
                    pass
            out.append(d)
        return out

    def get_relationships(
        self,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """Return all relationships for a project (from_name, to_name, type, metadata)."""
        with self._with_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT e1.name AS from_name, e2.name AS to_name, r.relationship_type, r.metadata
                FROM entity_relationships r
                JOIN entities e1 ON r.from_entity_id = e1.id
                JOIN entities e2 ON r.to_entity_id = e2.id
                WHERE r.project_id = ?
            """, (project_id,))
            rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("metadata"):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except (TypeError, json.JSONDecodeError):
                    pass
            out.append(d)
        return out

    def delete_project(self, project_id: str) -> None:
        """Remove all entities and relationships for a project."""
        with self._with_conn() as conn:
            conn.execute("DELETE FROM entity_relationships WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM entities WHERE project_id = ?", (project_id,))
        logger.info("entity_store_cleanup", project_id=project_id)


# -----------------------------------------------------------------------------
# MemoryManager — unified API
# -----------------------------------------------------------------------------


class MemoryManager:
    """
    Unified memory API: initialize stores, store/retrieve by type,
    entity lookup, project cleanup, and export for debugging.
    """

    def __init__(self) -> None:
        self._settings: Optional[MemorySettings] = None
        self._short: Optional[ShortTermStore] = None
        self._long: Optional[LongTermStore] = None
        self._entity: Optional[EntityStore] = None

    def initialize(self, settings: MemorySettings) -> None:
        """Set up all memory stores from settings."""
        self._settings = settings
        if not settings.memory_enabled:
            logger.info("memory_disabled")
            return
        self._short = ShortTermStore(
            chromadb_path=settings.chromadb_path,
            embedding_model=settings.embedding_model,
            collection_name=settings.collection_name,
            ollama_base_url=settings.ollama_base_url,
        )
        self._long = LongTermStore(
            sqlite_path=settings.sqlite_path,
            retention_days=settings.retention_days,
        )
        self._entity = EntityStore(sqlite_path=settings.sqlite_path)
        logger.info(
            "memory_initialized",
            chromadb_path=settings.chromadb_path,
            sqlite_path=settings.sqlite_path,
            share_between_crews=settings.share_between_crews,
        )

    @property
    def is_initialized(self) -> bool:
        """True if initialize() was called with memory_enabled=True."""
        return self._short is not None and self._long is not None and self._entity is not None

    @property
    def share_between_crews(self) -> bool:
        """Whether short-term memory is shared across crews in the same project."""
        return self._settings.share_between_crews if self._settings else True

    def store(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType,
        project_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Write to the appropriate store.

        - short_term: key = doc id, value = text (stored as embedding). project_id required.
        - long_term: key = subtype (conversation, metric, pattern), value = dict or str.
          For 'conversation', value should be {role, content}. For 'metric', {agent_role, model, metric_name, value}.
          For 'pattern', {pattern_type, content}.
        - entity: key = entity name, value = {type, attributes?}. project_id required.
        """
        if not self.is_initialized:
            return None
        if memory_type == "short_term":
            if not project_id:
                logger.warning("store_short_term_missing_project_id", key=key)
                return None
            text = value if isinstance(value, str) else json.dumps(value)
            self._short.add(project_id, key, text, metadata=kwargs.get("metadata"))
            return key
        if memory_type == "long_term":
            if isinstance(value, dict):
                subtype = value.get("_subtype") or kwargs.get("subtype", "conversation")
                if subtype == "conversation":
                    return self._long.add_conversation(
                        role=value.get("role", "user"),
                        content=value.get("content", json.dumps(value)),
                        project_id=project_id,
                    )
                if subtype == "metric":
                    self._long.add_metric(
                        agent_role=value.get("agent_role", ""),
                        model=value.get("model", ""),
                        metric_name=value.get("metric_name", ""),
                        value=float(value.get("value", 0)),
                    )
                    return key
                if subtype == "pattern":
                    return self._long.add_pattern(
                        pattern_type=value.get("pattern_type", "generic"),
                        content=value.get("content", json.dumps(value)),
                    )
            # Default: store as conversation
            content = value if isinstance(value, str) else json.dumps(value)
            return self._long.add_conversation(role="system", content=content, project_id=project_id)
        if memory_type == "entity":
            if not project_id:
                logger.warning("store_entity_missing_project_id", key=key)
                return None
            data = value if isinstance(value, dict) else {"type": "unknown", "attributes": {}}
            entity_type = data.get("type", "file")
            attrs = data.get("attributes", data)
            self._entity.upsert_entity(project_id, key, entity_type, attrs)
            return key
        return None

    def retrieve(
        self,
        query: str,
        memory_type: MemoryType,
        top_k: Optional[int] = None,
        project_id: Optional[str] = None,
    ) -> List[Any]:
        """
        Search with embeddings (short_term) or get recent (long_term).
        For short_term, project_id is required.
        """
        if not self.is_initialized:
            return []
        k = top_k or (self._settings.max_results if self._settings else 10)
        if memory_type == "short_term":
            if not project_id:
                return []
            hits = self._short.search(project_id, query, top_k=k)
            return [
                {"id": h[0], "document": h[1], "distance": h[2], "metadata": h[3]}
                for h in hits
            ]
        if memory_type == "long_term":
            conv = self._long.get_recent_conversations(limit=k, project_id=project_id)
            return [{"type": "conversation", "data": c} for c in conv]
        return []

    def get_entity(
        self,
        name: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Look up entity info by name and project."""
        if not self.is_initialized or not self._entity:
            return None
        return self._entity.get_entity(project_id, name)

    def cleanup(self, project_id: str) -> None:
        """Remove project-specific memory (short-term collection and entity store)."""
        if not self.is_initialized:
            return
        if self._short:
            self._short.delete_collection(project_id)
        if self._entity:
            self._entity.delete_project(project_id)
        logger.info("memory_cleanup", project_id=project_id)

    def export(self, project_id: str) -> Dict[str, Any]:
        """Dump project-related memory for debugging (short-term snippets + entities + recent convos)."""
        out: Dict[str, Any] = {
            "project_id": project_id,
            "short_term": [],
            "long_term_conversations": [],
            "entities": [],
            "relationships": [],
        }
        if not self.is_initialized:
            return out
        if self._short:
            try:
                coll = self._short.get_collection(project_id)
                got = coll.get(include=["documents", "metadatas"], limit=100)
                ids = got.get("ids") or []
                docs = got.get("documents") or []
                metas = got.get("metadatas") or []
                if docs and isinstance(docs[0], list):
                    docs = docs[0]
                if metas and isinstance(metas[0], list):
                    metas = metas[0]
                n = len(ids)
                out["short_term"] = [
                    {
                        "id": ids[i],
                        "document": docs[i] if i < len(docs) else "",
                        "metadata": metas[i] if i < len(metas) else {},
                    }
                    for i in range(n)
                ]
            except Exception as e:
                out["short_term_error"] = str(e)
        if self._long:
            out["long_term_conversations"] = self._long.get_recent_conversations(
                limit=50, project_id=project_id
            )
        if self._entity:
            out["entities"] = self._entity.get_entities(project_id)
            out["relationships"] = self._entity.get_relationships(project_id)
        return out

    def apply_retention(self) -> int:
        """Run long-term retention cleanup. Returns number of rows deleted."""
        if not self.is_initialized or not self._long:
            return 0
        return self._long.apply_retention()


def get_crew_embedder_config() -> Dict[str, Any]:
    """
    Build CrewAI embedder config from MemorySettings so crew memory uses Ollama (local).

    When passing memory=True to Crew(...), also pass embedder=get_crew_embedder_config()
    so CrewAI uses our local embedding model instead of default (OpenAI). Uses the same
    embedding_model and ollama_base_url as AI-Team short-term memory.
    """
    from ai_team.config.settings import get_settings

    m = get_settings().memory
    return {
        "provider": "ollama",
        "config": {
            "model_name": m.embedding_model,
            "url": m.ollama_base_url.rstrip("/"),
        },
    }


# Singleton for use across the app
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Return the global MemoryManager instance (creates one if needed)."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
