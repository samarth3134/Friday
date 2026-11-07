from datetime import datetime, timezone
from uuid import uuid4

import chromadb

from config import CHROMA_DB_PATH, MAX_MEMORY_RESULTS


COLLECTION_NAME = "friday_memory"
MEMORY_TYPES = {"conversation", "fact", "preference"}

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _memory_type(text, metadata):
    if metadata and metadata.get("type") in MEMORY_TYPES:
        return metadata["type"]

    normalized = text.strip().lower()
    if normalized.startswith("remember that"):
        return "preference"

    return "fact"


def _metadata(text, metadata=None):
    data = dict(metadata or {})
    data["timestamp"] = data.get("timestamp") or _now()
    data["type"] = _memory_type(text, data)
    return data


def save_memory(text, metadata=None):
    """Embed and store a memory locally in Chroma."""
    if not isinstance(text, str) or not text.strip():
        return None

    memory_id = str(uuid4())
    collection.add(
        ids=[memory_id],
        documents=[text.strip()],
        metadatas=[_metadata(text, metadata)],
    )
    return memory_id


def search_memory(query, n=MAX_MEMORY_RESULTS):
    """Return the most relevant memories for a query."""
    if not isinstance(query, str) or not query.strip():
        return []

    results = collection.query(
        query_texts=[query.strip()],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    memories = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for document, metadata, distance in zip(documents, metadatas, distances):
        memories.append(
            {
                "text": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return memories


def save_conversation(user_msg, friday_response):
    """Save both sides of a conversation pair."""
    if not isinstance(user_msg, str) or not isinstance(friday_response, str):
        return None

    user_text = user_msg.strip()
    friday_text = friday_response.strip()
    if not user_text and not friday_text:
        return None

    timestamp = _now()
    conversation_id = str(uuid4())

    user_id = str(uuid4())
    friday_id = str(uuid4())

    collection.add(
        ids=[user_id, friday_id],
        documents=[user_text, friday_text],
        metadatas=[
            {
                "timestamp": timestamp,
                "type": "conversation",
                "conversation_id": conversation_id,
                "role": "user",
                "order": 0,
            },
            {
                "timestamp": timestamp,
                "type": "conversation",
                "conversation_id": conversation_id,
                "role": "friday",
                "order": 1,
            },
        ],
    )

    # Explicit preferences are saved by the router. Logging an exchange must
    # not create a second preference or retry an unsuccessful save silently.
    return conversation_id


def get_recent(n=10):
    """Return the last n conversation pairs in chronological order."""
    records = collection.get(
        where={"type": "conversation"},
        include=["documents", "metadatas"],
    )

    pairs = {}
    for document, metadata in zip(records.get("documents", []), records.get("metadatas", [])):
        conversation_id = metadata.get("conversation_id")
        if not conversation_id:
            continue

        pair = pairs.setdefault(
            conversation_id,
            {
                "timestamp": metadata.get("timestamp", ""),
                "user": "",
                "friday": "",
            },
        )
        pair["timestamp"] = min(pair["timestamp"], metadata.get("timestamp", "")) if pair["timestamp"] else metadata.get("timestamp", "")

        if metadata.get("role") == "user":
            pair["user"] = document
        elif metadata.get("role") == "friday":
            pair["friday"] = document

    ordered_pairs = sorted(pairs.values(), key=lambda item: item["timestamp"])
    return ordered_pairs[-n:]
