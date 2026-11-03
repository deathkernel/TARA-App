"""Stable, read-only model catalogue helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tara_app.contracts import ModelInfo


class ModelCatalogueError(ValueError):
    """Raised when model selection filters are invalid."""


@dataclass(frozen=True)
class ModelQuery:
    provider_id: str | None = None
    family: str | None = None
    quantization_level: str | None = None
    text: str | None = None


class ModelCatalogue:
    """In-memory catalogue snapshot; it does not download or load model artifacts."""

    def __init__(self, models: Iterable[ModelInfo] = ()) -> None:
        self.replace(models)

    def replace(self, models: Iterable[ModelInfo]) -> None:
        snapshot = list(models)
        seen: set[tuple[str, str]] = set()
        for model in snapshot:
            if not isinstance(model, ModelInfo):
                raise ModelCatalogueError("catalogue entries must be ModelInfo records")
            if not model.provider_id.strip() or not model.name.strip():
                raise ModelCatalogueError("model provider and name must be non-empty")
            key = (model.provider_id, model.name)
            if key in seen:
                raise ModelCatalogueError("duplicate provider/model entry")
            seen.add(key)
        self._models = tuple(snapshot)

    def list(self, query: ModelQuery | None = None) -> list[ModelInfo]:
        query = query or ModelQuery()
        for field_name in ("provider_id", "family", "quantization_level", "text"):
            value = getattr(query, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ModelCatalogueError(f"{field_name} filter must be a non-empty string")
        result = []
        needle = query.text.casefold() if query.text else None
        for model in self._models:
            if query.provider_id and model.provider_id != query.provider_id:
                continue
            if query.family and model.family != query.family:
                continue
            if query.quantization_level and model.quantization_level != query.quantization_level:
                continue
            if needle and needle not in model.name.casefold() and needle not in (model.family or "").casefold():
                continue
            result.append(model)
        return result

    def get(self, provider_id: str, model_name: str) -> ModelInfo:
        matches = [m for m in self._models if m.provider_id == provider_id and m.name == model_name]
        if not matches:
            raise ModelCatalogueError("model is not present in the current catalogue snapshot")
        return matches[0]

    def __len__(self) -> int:
        return len(self._models)
