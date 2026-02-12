import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

# Disable Chroma telemetry before importing chromadb.
# `chromadb.telemetry.product.noop.Noop` is not available in every chromadb release,
# so only reference it when the module exists.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")
os.environ.setdefault("POSTHOG_DISABLED", "true")

NOOP_TELEMETRY_IMPL = "chromadb.telemetry.product.noop.Noop"
HAS_NOOP_TELEMETRY = find_spec("chromadb.telemetry.product.noop") is not None

if HAS_NOOP_TELEMETRY:
    os.environ.setdefault("CHROMA_PRODUCT_TELEMETRY_IMPL", NOOP_TELEMETRY_IMPL)
    os.environ.setdefault("CHROMA_TELEMETRY_IMPL", NOOP_TELEMETRY_IMPL)

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger(__name__)
# Suppress noisy telemetry logger even if a downstream dependency still attempts posthog calls
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


@dataclass
class RetrievedDocument:
    text: str
    metadata: dict[str, Any]
    distance: float | None = None


def _repair_legacy_collection_config(db_path: Path) -> bool:
    """Repair old Chroma configuration JSON rows missing required `_type` fields."""
    sqlite_path = db_path / "chroma.sqlite3"
    if not sqlite_path.exists():
        return False

    try:
        with sqlite3.connect(sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, config_json_str FROM collections WHERE config_json_str IS NOT NULL"
            )
            rows = cursor.fetchall()
            changed = 0

            for collection_id, config_json_str in rows:
                if not config_json_str:
                    continue
                try:
                    config = json.loads(config_json_str)
                except json.JSONDecodeError:
                    continue

                updated = False
                if isinstance(config, dict) and "_type" not in config:
                    config["_type"] = "CollectionConfigurationInternal"
                    updated = True

                hnsw_cfg = config.get("hnsw_configuration") if isinstance(config, dict) else None
                if isinstance(hnsw_cfg, dict) and "_type" not in hnsw_cfg:
                    hnsw_cfg["_type"] = "HNSWConfigurationInternal"
                    updated = True

                if updated:
                    cursor.execute(
                        "UPDATE collections SET config_json_str = ? WHERE id = ?",
                        (json.dumps(config), collection_id),
                    )
                    changed += 1

            if changed:
                conn.commit()
                logger.info("Repaired %s legacy Chroma collection config row(s).", changed)
            return changed > 0
    except Exception:
        logger.exception("Failed to repair legacy Chroma collection configuration.")
        return False


class ChromaRetriever:
    @staticmethod
    def _extract_business_key(question: str) -> str | None:
        match = re.search(r"\bFEA-\d+\b", question, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(0).upper()

    def _query_by_business_key_sqlite(self, business_key: str) -> list[RetrievedDocument]:
        sqlite_path = self._db_path / "chroma.sqlite3"
        if not sqlite_path.exists():
            return []

        try:
            with sqlite3.connect(sqlite_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM collections WHERE name = ?", (self._collection_name,))
                row = cur.fetchone()
                if not row:
                    return []
                collection_id = row[0]

                embedding_ids: list[str] = []
                sql_variants = [
                    (
                        """
                        SELECT em.id
                        FROM embedding_metadata em
                        JOIN embeddings e ON e.id = em.id
                        WHERE e.collection_id = ?
                          AND em.key = 'business_key'
                          AND em.string_value = ?
                        LIMIT ?
                        """,
                        (collection_id, business_key, self.top_k),
                    ),
                    (
                        """
                        SELECT em.id
                        FROM embedding_metadata em
                        JOIN embeddings e ON e.id = em.id
                        JOIN segments s ON s.id = e.segment_id
                        WHERE s.collection = ?
                          AND em.key = 'business_key'
                          AND em.string_value = ?
                        LIMIT ?
                        """,
                        (collection_id, business_key, self.top_k),
                    ),
                ]

                for sql, params in sql_variants:
                    try:
                        cur.execute(sql, params)
                        embedding_ids = [r[0] for r in cur.fetchall()]
                    except sqlite3.Error:
                        continue
                    if embedding_ids:
                        break

                if not embedding_ids:
                    return []

                placeholders = ",".join("?" for _ in embedding_ids)
                cur.execute(
                    f"""
                    SELECT id, key, string_value, int_value, float_value, bool_value
                    FROM embedding_metadata
                    WHERE id IN ({placeholders})
                    """,
                    embedding_ids,
                )
                metadata_rows = cur.fetchall()

            per_id: dict[str, dict[str, Any]] = {str(eid): {} for eid in embedding_ids}
            for emb_id, key, s_val, i_val, f_val, b_val in metadata_rows:
                emb_key = str(emb_id)
                if s_val is not None:
                    value: Any = s_val
                elif i_val is not None:
                    value = i_val
                elif f_val is not None:
                    value = f_val
                elif b_val is not None:
                    value = bool(b_val)
                else:
                    continue
                per_id.setdefault(emb_key, {})[str(key)] = value

            retrieved: list[RetrievedDocument] = []
            for emb_id in embedding_ids:
                meta = per_id.get(str(emb_id), {})
                text = str(meta.get("chroma:document", "")).strip()
                if not text:
                    text = str(meta.get("document", "")).strip()
                if not text:
                    continue

                cleaned_meta = {k: v for k, v in meta.items() if k != "chroma:document"}
                retrieved.append(
                    RetrievedDocument(text=text, metadata=cleaned_meta, distance=0.0)
                )

            if retrieved:
                logger.info(
                    "Resolved %s document(s) via SQLite metadata fallback for business_key=%s.",
                    len(retrieved),
                    business_key,
                )
            return retrieved
        except Exception as exc:
            logger.exception(
                "SQLite fallback lookup failed for business_key=%s: %s",
                business_key,
                exc,
            )
            return []

    def _query_by_business_key(self, business_key: str) -> list[RetrievedDocument]:
        if not self._collection:
            return []

        try:
            results = self._collection.get(
                where={"business_key": business_key},
                limit=self.top_k,
                include=["documents", "metadatas"],
            )

            documents = results.get("documents")
            metadatas = results.get("metadatas")
            if not isinstance(documents, list):
                return []

            retrieved: list[RetrievedDocument] = []
            for idx, text in enumerate(documents):
                if not text:
                    continue
                metadata = (
                    metadatas[idx]
                    if isinstance(metadatas, list) and idx < len(metadatas) and metadatas[idx]
                    else {}
                )
                retrieved.append(RetrievedDocument(text=text, metadata=metadata, distance=0.0))

            if retrieved:
                logger.info(
                    "Resolved %s document(s) via Chroma metadata fallback for business_key=%s.",
                    len(retrieved),
                    business_key,
                )
            return retrieved
        except Exception as exc:
            logger.warning(
                "Chroma metadata lookup failed for business_key=%s (%s); trying SQLite fallback.",
                business_key,
                exc,
            )
            return self._query_by_business_key_sqlite(business_key)

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        default_db_path = repo_root / "my_local_vectordb"

        db_path = Path(os.getenv("CHROMA_DB_PATH", str(default_db_path))).expanduser()
        collection_name = os.getenv("CHROMA_COLLECTION_NAME", "aida_knowledge_base")
        embedding_model = os.getenv(
            "CHROMA_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        embedding_local_only = (
            os.getenv("CHROMA_EMBEDDING_LOCAL_ONLY", "true").lower() == "true"
        )

        self.enabled = os.getenv("RAG_ENABLED", "true").lower() == "true"
        self.top_k = int(os.getenv("RAG_TOP_K", "4"))
        self.max_context_chars = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "5000"))
        self._db_path = db_path
        self._collection_name = collection_name

        self._collection: Collection | None = None

        if not self.enabled:
            logger.info("RAG is disabled via RAG_ENABLED.")
            return

        if not db_path.exists():
            logger.warning("Chroma DB path does not exist: %s", db_path)
            return

        try:
            settings_kwargs: dict[str, Any] = {"anonymized_telemetry": False}
            if HAS_NOOP_TELEMETRY:
                settings_kwargs["chroma_product_telemetry_impl"] = NOOP_TELEMETRY_IMPL

            client = chromadb.PersistentClient(
                path=str(db_path),
                settings=Settings(**settings_kwargs),
            )

            if embedding_local_only:
                # Fail fast when the model is not already present locally.
                # This avoids long startup delays/timeouts in restricted networks.
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

            emb_fn = SentenceTransformerEmbeddingFunction(model_name=embedding_model)
            try:
                self._collection = client.get_collection(
                    name=collection_name,
                    embedding_function=emb_fn,
                )
            except KeyError as exc:
                if str(exc) != "'_type'":
                    raise

                if _repair_legacy_collection_config(db_path):
                    logger.warning(
                        "Detected legacy Chroma collection configuration without '_type'. "
                        "Applied one-time local SQLite repair and retrying collection load."
                    )
                    self._collection = client.get_collection(
                        name=collection_name,
                        embedding_function=emb_fn,
                    )
                else:
                    raise

            logger.info(
                "Connected to Chroma collection '%s' at %s using embedding model '%s' (local_only=%s).",
                collection_name,
                db_path,
                embedding_model,
                embedding_local_only,
            )
        except Exception as exc:
            logger.exception(
                "Failed to initialize Chroma retriever: %s. "
                "If you are offline/proxy-restricted, pre-download the embedding model and set "
                "CHROMA_EMBEDDING_MODEL to a local path, or set CHROMA_EMBEDDING_LOCAL_ONLY=false.",
                exc,
            )
            self._collection = None

    @property
    def is_ready(self) -> bool:
        return self.enabled and self._collection is not None

    @staticmethod
    def _first_result_group(results: dict[str, Any], key: str) -> list[Any]:
        data = results.get(key)
        if not isinstance(data, list) or not data:
            return []
        first = data[0]
        return first if isinstance(first, list) else []

    def query(self, question: str) -> list[RetrievedDocument]:
        if not self.is_ready or not question.strip():
            return []

        business_key = self._extract_business_key(question)
        if business_key:
            exact_hits = self._query_by_business_key(business_key)
            if exact_hits:
                return exact_hits

        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=self.top_k,
                include=["documents", "metadatas", "distances"],
            )
        except AttributeError as exc:
            if "dimensionality" in str(exc):
                logger.warning(
                    "Vector query failed due to legacy HNSW persistence format mismatch; falling back to metadata lookup when possible."
                )
                if business_key:
                    return self._query_by_business_key(business_key)
                return []
            logger.exception("Chroma query failed: %s", exc)
            return []
        except Exception as exc:
            logger.exception("Chroma query failed: %s", exc)
            return []

        documents = self._first_result_group(results, "documents")
        metadatas = self._first_result_group(results, "metadatas")
        distances = self._first_result_group(results, "distances")

        retrieved: list[RetrievedDocument] = []
        for idx, text in enumerate(documents):
            if not text:
                continue
            metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
            distance = distances[idx] if idx < len(distances) else None
            retrieved.append(
                RetrievedDocument(text=text, metadata=metadata, distance=distance)
            )

        return retrieved


def build_rag_context(docs: list[RetrievedDocument], max_chars: int) -> str:
    if not docs:
        return ""

    chunks: list[str] = []
    total_chars = 0

    for rank, doc in enumerate(docs, start=1):
        item = (
            f"[Context #{rank}]\n"
            f"document: {doc.text}\n"
            f"metadata: {doc.metadata}\n"
            f"distance: {doc.distance}\n"
        )
        if total_chars + len(item) > max_chars:
            break
        chunks.append(item)
        total_chars += len(item)

    return "\n".join(chunks)


def build_rag_system_instruction(context: str) -> str:
    return (
        "You are an automotive assistant operating in strict RAG mode. "
        "Use ONLY the provided retrieval context to answer. "
        "If context is insufficient, explicitly state that the knowledge base does not contain enough information.\n\n"
        "Retrieved context:\n"
        f"{context}"
    )