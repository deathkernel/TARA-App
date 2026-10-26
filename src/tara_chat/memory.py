"""Small memory primitives for TARA.

Research basis:
- Graves et al. (2014), Neural Turing Machines: neural systems can be paired
  with external memory through an explicit read/write interface.
- Lewis et al. (2020), Retrieval-Augmented Generation: non-parametric external
  memory can complement parametric model knowledge.
- Recent agent-memory work treats memory as a dynamic system: memories are
  formed, retrieved, updated, and forgotten over time.

TARA keeps retrieval and memory dynamics deliberately small and inspectable:
lexical relevance scoring, explicit updates, access tracking, and deterministic
capacity-based forgetting. This is a foundation for later learned retrieval,
not a claim to reproduce biological memory.
"""

import json
import math
import re
from collections import deque
from pathlib import Path

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text):
    """Return normalized lexical tokens from a string."""
    return _TOKEN_RE.findall(str(text).lower())


def lexical_relevance(query, text):
    """Score query/text relevance using normalized token overlap.

    The score is in [0, 1]: the fraction of unique query tokens also present
    in the candidate text. Repeated tokens do not artificially increase the
    score, keeping the method deterministic and easy to inspect.
    """
    query_tokens = set(_tokens(query))
    text_tokens = set(_tokens(text))
    if not query_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


class WorkingMemory:
    """Bounded FIFO working memory for recent observations or thoughts."""

    def __init__(self, capacity=8):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self._items = deque(maxlen=self.capacity)

    def add(self, item):
        self._items.append(item)

    def recent(self, limit=None):
        """Return recent items in oldest-to-newest order."""
        items = list(self._items)
        if limit is None:
            return items
        if limit < 0:
            raise ValueError("limit must be non-negative")
        return items[-limit:] if limit else []

    def clear(self):
        self._items.clear()

    def __len__(self):
        return len(self._items)


class LongTermMemory:
    """Persistent memory with retrieval, update tracking, and forgetting."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self._records = {}
        self._metadata = {}
        self._next_order = 0
        if self.path is not None and self.path.exists():
            self.load()

    def remember(self, key, value, importance=1.0):
        """Create or update a memory and return its current value.

        Updating an existing key preserves its access history and insertion
        order. Importance is a deterministic forgetting signal in [0, +inf).
        """
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        if not isinstance(importance, (int, float)) or not math.isfinite(importance):
            raise ValueError("importance must be finite")
        if importance < 0:
            raise ValueError("importance must be non-negative")

        metadata = self._metadata.get(key)
        if metadata is None:
            metadata = {"access_count": 0, "importance": float(importance), "order": self._next_order}
            self._next_order += 1
            self._metadata[key] = metadata
        else:
            metadata["importance"] = float(importance)
        self._records[key] = value
        return value

    def recall(self, key, default=None):
        value = self._records.get(key, default)
        if key in self._records:
            self._metadata[key]["access_count"] += 1
        return value

    def retrieve(self, query, limit=None, min_score=0.0):
        """Return memories ranked by lexical relevance, then deterministic order.

        Each result contains ``key``, ``value``, and ``score``. Retrieved
        memories have their access count incremented, which supplies a simple
        usage signal for later forgetting decisions.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [0, 1]")

        ranked = []
        for key, value in self._records.items():
            score = lexical_relevance(query, f"{key} {value}")
            if score >= min_score and score > 0.0:
                ranked.append((score, self._metadata[key]["order"], key, value))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        if limit is not None:
            ranked = ranked[:limit]

        results = []
        for score, _, key, value in ranked:
            self._metadata[key]["access_count"] += 1
            results.append({"key": key, "value": value, "score": score})
        return results

    def forget(self, key):
        """Remove one memory and return its value, if present."""
        value = self._records.pop(key, None)
        self._metadata.pop(key, None)
        return value

    def forget_least_used(self, max_records):
        """Deterministically trim memory to at most ``max_records`` entries.

        Lower access count is forgotten first; importance breaks ties in favor
        of retaining more important memories, then older insertion order is
        forgotten first. Returns the forgotten keys in removal order.
        """
        if max_records < 0:
            raise ValueError("max_records must be non-negative")
        excess = len(self._records) - max_records
        if excess <= 0:
            return []

        candidates = sorted(
            self._records,
            key=lambda key: (
                self._metadata[key]["access_count"],
                self._metadata[key]["importance"],
                self._metadata[key]["order"],
            ),
        )
        forgotten = candidates[:excess]
        for key in forgotten:
            self.forget(key)
        return forgotten

    def keys(self):
        return list(self._records.keys())

    def metadata(self, key):
        """Return a copy of deterministic memory metadata."""
        if key not in self._records:
            return None
        return dict(self._metadata[key])

    def save(self, path=None):
        destination = Path(path) if path is not None else self.path
        if destination is None:
            raise ValueError("a path is required to save long-term memory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": 2,
            "records": self._records,
            "metadata": self._metadata,
            "next_order": self._next_order,
        }
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.path = destination

    def load(self, path=None):
        source = Path(path) if path is not None else self.path
        if source is None:
            raise ValueError("a path is required to load long-term memory")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("long-term memory must contain a JSON object")

        if payload.get("format_version") == 2:
            records = payload.get("records")
            metadata = payload.get("metadata", {})
            if not isinstance(records, dict) or not isinstance(metadata, dict):
                raise ValueError("invalid long-term memory format")
            self._records = records
            self._metadata = metadata
            self._next_order = int(payload.get("next_order", len(records)))
            for order, key in enumerate(self._records):
                self._metadata.setdefault(
                    key,
                    {"access_count": 0, "importance": 1.0, "order": order},
                )
            return

        # Backward-compatible loading of the original plain key/value format.
        self._records = payload
        self._metadata = {}
        for order, key in enumerate(self._records):
            self._metadata[key] = {"access_count": 0, "importance": 1.0, "order": order}
        self._next_order = len(self._records)
        self.path = source
