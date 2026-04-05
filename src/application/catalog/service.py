from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evo_system.experimental_space.asset_loader import ASSETS_ROOT
from evo_system.experimental_space.catalog_service import CatalogEntry, CatalogService


@dataclass(frozen=True)
class ApplicationCatalogItem:
    """External-facing catalog record for future API/UI consumers."""

    id: str
    category: str
    origin: str
    file_path: str | None = None
    description: str | None = None
    payload: dict[str, Any] | None = None

    @classmethod
    def from_core_entry(
        cls,
        *,
        category: str,
        entry: CatalogEntry,
    ) -> "ApplicationCatalogItem":
        return cls(
            id=entry.id,
            category=category,
            origin=entry.origin,
            file_path=entry.file_path,
            description=entry.description,
            payload=dict(entry.payload) if entry.payload is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "origin": self.origin,
            "file_path": self.file_path,
            "description": self.description,
            "payload": dict(self.payload) if self.payload is not None else None,
        }


@dataclass(frozen=True)
class ApplicationCatalogSnapshot:
    """Serializable application-facing view over the experimental catalog."""

    signal_plugins: tuple[ApplicationCatalogItem, ...]
    policy_engines: tuple[ApplicationCatalogItem, ...]
    gene_type_definitions: tuple[ApplicationCatalogItem, ...]
    signal_packs: tuple[ApplicationCatalogItem, ...]
    genome_schemas: tuple[ApplicationCatalogItem, ...]
    decision_policies: tuple[ApplicationCatalogItem, ...]
    mutation_profiles: tuple[ApplicationCatalogItem, ...]
    experiment_presets: tuple[ApplicationCatalogItem, ...]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "signal_plugins": [item.to_dict() for item in self.signal_plugins],
            "policy_engines": [item.to_dict() for item in self.policy_engines],
            "gene_type_definitions": [
                item.to_dict() for item in self.gene_type_definitions
            ],
            "signal_packs": [item.to_dict() for item in self.signal_packs],
            "genome_schemas": [item.to_dict() for item in self.genome_schemas],
            "decision_policies": [item.to_dict() for item in self.decision_policies],
            "mutation_profiles": [item.to_dict() for item in self.mutation_profiles],
            "experiment_presets": [item.to_dict() for item in self.experiment_presets],
        }


class ExperimentalCatalogApplicationService:
    """Small application boundary over the internal experimental catalog.

    This layer exists so future CLI/API/UI code does not need to depend
    directly on internal `experimental_space` service types.

    Transitional note:
    - This is intentionally a thin read-only adapter, not the final shape of
      the application layer.
    - Future work will likely add more focused application services and
      explicit response models per use case instead of routing everything
      through one generic catalog payload.
    """

    def __init__(
        self,
        *,
        asset_root: Path = ASSETS_ROOT,
        core_service: CatalogService | None = None,
    ) -> None:
        self._core_service = core_service or CatalogService(asset_root=asset_root)

    def get_catalog_snapshot(self) -> ApplicationCatalogSnapshot:
        core_snapshot = self._core_service.get_catalog_snapshot()
        return ApplicationCatalogSnapshot(
            signal_plugins=self._map_category(
                "signal_plugins",
                core_snapshot.signal_plugins,
            ),
            policy_engines=self._map_category(
                "policy_engines",
                core_snapshot.policy_engines,
            ),
            gene_type_definitions=self._map_category(
                "gene_type_definitions",
                core_snapshot.gene_type_definitions,
            ),
            signal_packs=self._map_category("signal_packs", core_snapshot.signal_packs),
            genome_schemas=self._map_category(
                "genome_schemas",
                core_snapshot.genome_schemas,
            ),
            decision_policies=self._map_category(
                "decision_policies",
                core_snapshot.decision_policies,
            ),
            mutation_profiles=self._map_category(
                "mutation_profiles",
                core_snapshot.mutation_profiles,
            ),
            experiment_presets=self._map_category(
                "experiment_presets",
                core_snapshot.experiment_presets,
            ),
        )

    def get_catalog_payload(self) -> dict[str, list[dict[str, Any]]]:
        return self.get_catalog_snapshot().to_dict()

    def get_catalog_category_payload(self, category: str) -> list[dict[str, Any]]:
        payload = self.get_catalog_payload()
        try:
            return payload[category]
        except KeyError as exc:
            raise KeyError(f"Unknown catalog category: {category}") from exc

    def _map_category(
        self,
        category: str,
        entries: tuple[CatalogEntry, ...],
    ) -> tuple[ApplicationCatalogItem, ...]:
        return tuple(
            ApplicationCatalogItem.from_core_entry(category=category, entry=entry)
            for entry in entries
        )
