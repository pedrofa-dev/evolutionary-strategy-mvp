from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evo_system.experimental_space.asset_loader import (
    ASSETS_ROOT,
    DeclarativeAsset,
    load_all_declarative_assets,
)
from evo_system.experimental_space.defaults import (
    decision_policy_registry,
    genome_schema_registry,
    mutation_profile_registry,
    policy_engine_registry,
    signal_pack_registry,
)
from evo_system.experimental_space.gene_catalog import GeneTypeDefinition
from evo_system.experimentation.presets import PRESET_REGISTRY
from evo_system.experimentation.presets import describe_preset


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CatalogEntry:
    """Small serializable catalog record for future CLI/API/UI layers."""

    id: str
    type: str
    origin: str
    file_path: str | None = None
    description: str | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "origin": self.origin,
            "file_path": self.file_path,
            "description": self.description,
            "payload": dict(self.payload) if self.payload is not None else None,
        }


@dataclass(frozen=True)
class CatalogSnapshot:
    """Stable aggregate view over experimental-space modules and assets."""

    signal_plugins: tuple[CatalogEntry, ...]
    policy_engines: tuple[CatalogEntry, ...]
    gene_type_definitions: tuple[CatalogEntry, ...]
    signal_packs: tuple[CatalogEntry, ...]
    genome_schemas: tuple[CatalogEntry, ...]
    decision_policies: tuple[CatalogEntry, ...]
    mutation_profiles: tuple[CatalogEntry, ...]
    experiment_presets: tuple[CatalogEntry, ...]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "signal_plugins": [entry.to_dict() for entry in self.signal_plugins],
            "policy_engines": [entry.to_dict() for entry in self.policy_engines],
            "gene_type_definitions": [
                entry.to_dict() for entry in self.gene_type_definitions
            ],
            "signal_packs": [entry.to_dict() for entry in self.signal_packs],
            "genome_schemas": [entry.to_dict() for entry in self.genome_schemas],
            "decision_policies": [entry.to_dict() for entry in self.decision_policies],
            "mutation_profiles": [entry.to_dict() for entry in self.mutation_profiles],
            "experiment_presets": [entry.to_dict() for entry in self.experiment_presets],
        }


class CatalogService:
    """Read-only catalog surface over built-in modules plus declarative assets.

    This service is intentionally simple:
    - it reuses existing registries and asset loading
    - it does not attempt deep compatibility resolution
    - it returns small serializable records for future UI/API layers
    """

    def __init__(self, *, asset_root: Path = ASSETS_ROOT) -> None:
        self.asset_root = asset_root

    def list_signal_plugins(self) -> list[CatalogEntry]:
        return []

    def list_policy_engines(self) -> list[CatalogEntry]:
        return self._registry_entries(
            registry=policy_engine_registry,
            entry_type="policy_engine",
            origin="plugin",
            payload_builder=lambda item: {
                "name": item.name,
                "builds_decision_policy": item.build_decision_policy().name,
            },
        )

    def list_gene_type_definitions(self) -> list[CatalogEntry]:
        entries: list[CatalogEntry] = []
        seen_ids: set[str] = set()

        for schema_name in genome_schema_registry.list():
            schema = genome_schema_registry.get(schema_name)
            catalog = schema.get_gene_type_catalog()
            for definition in catalog.describe_gene_types():
                definition_id = definition.name
                if definition_id in seen_ids:
                    continue
                seen_ids.add(definition_id)
                entries.append(
                    CatalogEntry(
                        id=definition_id,
                        type="gene_type_definition",
                        origin="runtime",
                        file_path=_relative_source_path(catalog),
                        payload=_gene_type_definition_payload(
                            definition=definition,
                            gene_catalog_name=catalog.name,
                        ),
                    )
                )

        return _sort_entries(entries)

    def list_signal_packs(self) -> list[CatalogEntry]:
        return _sort_entries(
            self._registry_entries(
                registry=signal_pack_registry,
                entry_type="signal_pack",
                origin="runtime",
                payload_builder=lambda item: {
                    "name": item.name,
                    "feature_names": list(item.feature_names),
                    "family_names": list(item.family_names),
                },
            )
            + self._asset_entries("signal_packs", "signal_pack")
        )

    def list_genome_schemas(self) -> list[CatalogEntry]:
        return _sort_entries(
            self._registry_entries(
                registry=genome_schema_registry,
                entry_type="genome_schema",
                origin="runtime",
                payload_builder=lambda item: {
                    "name": item.name,
                    "module_names": list(item.get_module_names()),
                    "gene_catalog_name": item.get_gene_type_catalog().name,
                },
            )
            + self._asset_entries("genome_schemas", "genome_schema")
        )

    def list_decision_policies(self) -> list[CatalogEntry]:
        return _sort_entries(
            self._registry_entries(
                registry=decision_policy_registry,
                entry_type="decision_policy",
                origin="runtime",
                payload_builder=lambda item: {"name": item.name},
            )
            + self._asset_entries("decision_policies", "decision_policy")
        )

    def list_mutation_profiles(self) -> list[CatalogEntry]:
        return _sort_entries(
            self._registry_entries(
                registry=mutation_profile_registry,
                entry_type="mutation_profile",
                origin="runtime",
                payload_builder=lambda item: {"name": item.name},
            )
            + self._asset_entries("mutation_profiles", "mutation_profile")
        )

    def list_experiment_presets(self) -> list[CatalogEntry]:
        return _sort_entries(
            self._registry_entries(
                registry=PRESET_REGISTRY,
                entry_type="experiment_preset",
                origin="runtime",
                description_builder=lambda item_name, item: describe_preset(item_name),
                payload_builder=lambda item: {
                    "name": item.name,
                    "generations": item.generations,
                    "max_seeds": item.max_seeds,
                    "seeds": list(item.seeds) if item.seeds is not None else None,
                },
            )
            + self._asset_entries("experiment_presets", "experiment_preset")
        )

    def get_catalog_snapshot(self) -> CatalogSnapshot:
        return CatalogSnapshot(
            signal_plugins=tuple(self.list_signal_plugins()),
            policy_engines=tuple(self.list_policy_engines()),
            gene_type_definitions=tuple(self.list_gene_type_definitions()),
            signal_packs=tuple(self.list_signal_packs()),
            genome_schemas=tuple(self.list_genome_schemas()),
            decision_policies=tuple(self.list_decision_policies()),
            mutation_profiles=tuple(self.list_mutation_profiles()),
            experiment_presets=tuple(self.list_experiment_presets()),
        )

    def _asset_entries(self, asset_type: str, entry_type: str) -> list[CatalogEntry]:
        assets = load_all_declarative_assets(self.asset_root).get(asset_type, [])
        return [
            CatalogEntry(
                id=asset.name,
                type=entry_type,
                origin="asset",
                file_path=_relative_path(asset.path),
                description=_description_from_payload(asset.payload),
                payload=dict(asset.payload),
            )
            for asset in assets
        ]

    def _registry_entries(
        self,
        *,
        registry: Any,
        entry_type: str,
        origin: str,
        description_builder: Any = None,
        payload_builder: Any = None,
    ) -> list[CatalogEntry]:
        entries: list[CatalogEntry] = []
        for item_name in registry.list():
            item = registry.get(item_name)
            payload = payload_builder(item) if payload_builder is not None else None
            description = (
                description_builder(item_name, item)
                if description_builder is not None
                else _docstring_summary(item)
            )
            entries.append(
                CatalogEntry(
                    id=item_name,
                    type=entry_type,
                    origin=origin,
                    file_path=_relative_source_path(item),
                    description=description,
                    payload=payload,
                )
            )
        return entries


def _gene_type_definition_payload(
    *,
    definition: GeneTypeDefinition,
    gene_catalog_name: str,
) -> dict[str, Any]:
    payload = definition.to_dict()
    payload["gene_catalog_name"] = gene_catalog_name
    return payload


def _sort_entries(entries: list[CatalogEntry]) -> list[CatalogEntry]:
    return sorted(entries, key=lambda entry: (entry.type, entry.origin, entry.id))


def _relative_source_path(item: Any) -> str | None:
    source_path = inspect.getsourcefile(item.__class__)
    if source_path is None:
        return None
    return _relative_path(Path(source_path))


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _docstring_summary(item: Any) -> str | None:
    docstring = inspect.getdoc(item.__class__) or inspect.getdoc(item)
    if not docstring:
        return None
    return docstring.strip().splitlines()[0].strip()


def _description_from_payload(payload: dict[str, Any]) -> str | None:
    description = payload.get("description")
    if isinstance(description, str) and description.strip():
        return description
    return None
