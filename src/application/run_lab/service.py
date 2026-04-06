from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.catalog import ExperimentalCatalogApplicationService
from application.execution_queue import ExecutionQueueService, SubmittedRunQueueJobResult
from evo_system.experimental_space.asset_loader import (
    ASSETS_ROOT,
    load_declarative_asset,
)
from evo_system.data_ingestion.dataset_builder.dataset_catalog import parse_manifest
from evo_system.experimental_space.catalog_service import CatalogService
from evo_system.experimental_space.gene_catalog import get_gene_catalog
from evo_system.experimental_space.identity import (
    build_experimental_space_snapshot_from_config_snapshot,
)
from evo_system.experimental_space.defaults import get_default_signal_pack
from evo_system.experimentation.presets import (
    PRESET_REGISTRY,
    describe_preset,
)
from evo_system.storage import CURRENT_LOGIC_VERSION, DEFAULT_PERSISTENCE_DB_PATH


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_CONFIGS_DIR = REPO_ROOT / "configs" / "runs"
DATASET_CONFIGS_DIR = REPO_ROOT / "configs" / "datasets"
RUN_LAB_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "ui_run_lab"
SIGNAL_PACK_ASSETS_DIR = ASSETS_ROOT / "signal_packs"
GENOME_SCHEMA_ASSETS_DIR = ASSETS_ROOT / "genome_schemas"
MUTATION_PROFILE_ASSETS_DIR = ASSETS_ROOT / "mutation_profiles"
DEFAULT_EXECUTION_PRESET = "standard"


def _canonicalize_json_payload(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class RunLabDatasetCatalogSummary:
    id: str
    description: str
    market_type: str
    timeframe: str
    asset_symbols: tuple[str, ...]
    date_range_start: str
    date_range_end: str
    split_summary: dict[str, int]
    sample_dataset_ids: dict[str, tuple[str, ...]]
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "market_type": self.market_type,
            "timeframe": self.timeframe,
            "asset_symbols": list(self.asset_symbols),
            "date_range_start": self.date_range_start,
            "date_range_end": self.date_range_end,
            "split_summary": dict(self.split_summary),
            "sample_dataset_ids": {
                key: list(value) for key, value in self.sample_dataset_ids.items()
            },
            "file_path": self.file_path,
        }


@dataclass(frozen=True)
class RunLabOption:
    id: str
    label: str
    description: str | None
    origin: str
    classification: str
    selectable: bool
    warning: str | None
    file_path: str | None = None
    engine_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "origin": self.origin,
            "classification": self.classification,
            "selectable": self.selectable,
            "warning": self.warning,
            "file_path": self.file_path,
            "engine_name": self.engine_name,
        }


@dataclass(frozen=True)
class RunLabTemplateSummary:
    id: str
    label: str
    file_path: str
    dataset_catalog_id: str
    signal_pack_name: str
    genome_schema_name: str
    decision_policy_name: str
    mutation_profile_name: str
    seed_mode: str
    seed_start: int | None
    seed_count: int | None
    explicit_seeds: tuple[int, ...]
    generations_planned: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "file_path": self.file_path,
            "dataset_catalog_id": self.dataset_catalog_id,
            "signal_pack_name": self.signal_pack_name,
            "genome_schema_name": self.genome_schema_name,
            "decision_policy_name": self.decision_policy_name,
            "mutation_profile_name": self.mutation_profile_name,
            "seed_mode": self.seed_mode,
            "seed_start": self.seed_start,
            "seed_count": self.seed_count,
            "explicit_seeds": list(self.explicit_seeds),
            "generations_planned": self.generations_planned,
        }


@dataclass(frozen=True)
class SignalAuthoringOption:
    id: str
    label: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class SignalPackAuthoringMetadata:
    signal_options: tuple[SignalAuthoringOption, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_options": [item.to_dict() for item in self.signal_options],
        }


@dataclass(frozen=True)
class GenomeSchemaAuthoringOption:
    id: str
    label: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class GenomeSchemaSuggestedModule:
    name: str
    gene_type: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gene_type": self.gene_type,
            "required": self.required,
        }


@dataclass(frozen=True)
class GenomeSchemaAuthoringMetadata:
    gene_catalog_options: tuple[GenomeSchemaAuthoringOption, ...]
    gene_type_options: tuple[GenomeSchemaAuthoringOption, ...]
    suggested_modules: tuple[GenomeSchemaSuggestedModule, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_catalog_options": [
                item.to_dict() for item in self.gene_catalog_options
            ],
            "gene_type_options": [item.to_dict() for item in self.gene_type_options],
            "suggested_modules": [item.to_dict() for item in self.suggested_modules],
        }


@dataclass(frozen=True)
class RunLabBootstrap:
    current_logic_version: str
    dataset_catalogs: tuple[RunLabDatasetCatalogSummary, ...]
    signal_packs: tuple[RunLabOption, ...]
    genome_schemas: tuple[RunLabOption, ...]
    mutation_profiles: tuple[RunLabOption, ...]
    decision_policies: tuple[RunLabOption, ...]
    execution_presets: tuple[RunLabOption, ...]
    config_templates: tuple[RunLabTemplateSummary, ...]
    signal_pack_authoring: SignalPackAuthoringMetadata
    genome_schema_authoring: GenomeSchemaAuthoringMetadata
    defaults: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_logic_version": self.current_logic_version,
            "dataset_catalogs": [item.to_dict() for item in self.dataset_catalogs],
            "signal_packs": [item.to_dict() for item in self.signal_packs],
            "genome_schemas": [item.to_dict() for item in self.genome_schemas],
            "mutation_profiles": [item.to_dict() for item in self.mutation_profiles],
            "decision_policies": [item.to_dict() for item in self.decision_policies],
            "execution_presets": [item.to_dict() for item in self.execution_presets],
            "config_templates": [item.to_dict() for item in self.config_templates],
            "signal_pack_authoring": self.signal_pack_authoring.to_dict(),
            "genome_schema_authoring": self.genome_schema_authoring.to_dict(),
            "defaults": dict(self.defaults),
        }


@dataclass(frozen=True)
class SavedRunConfigResult:
    config_name: str
    config_path: str
    config_payload: dict[str, Any]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "config_path": self.config_path,
            "config_payload": dict(self.config_payload),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class SavedMutationProfileAssetResult:
    asset_id: str
    asset_path: str
    asset_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_path": self.asset_path,
            "asset_payload": dict(self.asset_payload),
        }


@dataclass(frozen=True)
class SavedSignalPackAssetResult:
    asset_id: str
    asset_path: str
    asset_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_path": self.asset_path,
            "asset_payload": dict(self.asset_payload),
        }


@dataclass(frozen=True)
class SavedGenomeSchemaAssetResult:
    asset_id: str
    asset_path: str
    asset_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_path": self.asset_path,
            "asset_payload": dict(self.asset_payload),
        }


LaunchedRunResult = SubmittedRunQueueJobResult


class RunLabApplicationService:
    """Small application service for the first operational UI tab.

    This service stays intentionally conservative:
    - it reads canonical dataset manifests and active run-config templates
    - it saves canonical JSON configs under `configs/runs/`
    - it launches the existing multiseed script instead of inventing a new
      execution path
    """

    def __init__(
        self,
        *,
        repo_root: Path = REPO_ROOT,
        dataset_configs_dir: Path = DATASET_CONFIGS_DIR,
        run_configs_dir: Path = RUN_CONFIGS_DIR,
        run_lab_artifacts_dir: Path = RUN_LAB_ARTIFACTS_DIR,
        signal_pack_assets_dir: Path = SIGNAL_PACK_ASSETS_DIR,
        genome_schema_assets_dir: Path = GENOME_SCHEMA_ASSETS_DIR,
        mutation_profile_assets_dir: Path = MUTATION_PROFILE_ASSETS_DIR,
        database_path: str | Path | None = None,
        catalog_service: CatalogService | None = None,
        launcher: Any = None,
        queue_service: ExecutionQueueService | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.dataset_configs_dir = dataset_configs_dir
        self.run_configs_dir = run_configs_dir
        self.run_lab_artifacts_dir = run_lab_artifacts_dir
        self.signal_pack_assets_dir = signal_pack_assets_dir
        self.genome_schema_assets_dir = genome_schema_assets_dir
        self.mutation_profile_assets_dir = mutation_profile_assets_dir
        asset_root = (
            mutation_profile_assets_dir.parent
            if mutation_profile_assets_dir != MUTATION_PROFILE_ASSETS_DIR
            else (
                genome_schema_assets_dir.parent
                if genome_schema_assets_dir != GENOME_SCHEMA_ASSETS_DIR
                else signal_pack_assets_dir.parent
            )
        )
        self.catalog_service = catalog_service or CatalogService(
            asset_root=asset_root
        )
        resolved_database_path = (
            Path(database_path)
            if database_path is not None
            else repo_root / DEFAULT_PERSISTENCE_DB_PATH
        )
        self.queue_service = queue_service or ExecutionQueueService(
            database_path=resolved_database_path,
            repo_root=repo_root,
            run_lab_artifacts_dir=run_lab_artifacts_dir,
            launcher=launcher,
        )

    def get_bootstrap(self) -> RunLabBootstrap:
        dataset_catalogs = self._list_dataset_catalogs()
        signal_packs = self._build_runtime_options("signal_packs")
        genome_schemas = self._build_runtime_options("genome_schemas")
        mutation_profiles = self._build_runtime_options("mutation_profiles")
        decision_policies = self._build_runtime_options("decision_policies")
        execution_presets = self._build_execution_presets()
        config_templates = self._list_config_templates()
        signal_pack_authoring = self._build_signal_pack_authoring_metadata()
        genome_schema_authoring = self._build_genome_schema_authoring_metadata()
        default_template = self._select_default_template(config_templates)
        default_execution_preset = self._select_default_execution_preset(
            execution_presets
        )

        defaults = {
            "template_config_name": default_template.id,
            "dataset_catalog_id": default_template.dataset_catalog_id,
            "signal_pack_name": default_template.signal_pack_name,
            "genome_schema_name": default_template.genome_schema_name,
            "mutation_profile_name": default_template.mutation_profile_name,
            "decision_policy_name": default_template.decision_policy_name,
            "seed_mode": default_template.seed_mode,
            "seed_start": default_template.seed_start,
            "seed_count": default_template.seed_count,
            "explicit_seeds": list(default_template.explicit_seeds),
            "generations_planned": default_template.generations_planned,
            "experiment_preset_name": default_execution_preset.id,
            "parallel_workers": 1,
            "queue_concurrency_limit": self.queue_service.get_concurrency_limit(),
        }

        return RunLabBootstrap(
            current_logic_version=CURRENT_LOGIC_VERSION,
            dataset_catalogs=dataset_catalogs,
            signal_packs=signal_packs,
            genome_schemas=genome_schemas,
            mutation_profiles=mutation_profiles,
            decision_policies=decision_policies,
            execution_presets=execution_presets,
            config_templates=config_templates,
            signal_pack_authoring=signal_pack_authoring,
            genome_schema_authoring=genome_schema_authoring,
            defaults=defaults,
        )

    def save_run_config(self, payload: dict[str, Any]) -> SavedRunConfigResult:
        """Write a canonical run config under configs/runs/.

        This is the current canonical write path used by the UI/API layer.
        Integrity rules such as config-name collision handling live here so
        they are not enforced only in the frontend.
        """
        template_path = self._resolve_template_path(str(payload["template_config_name"]))
        base_config = json.loads(template_path.read_text(encoding="utf-8"))
        config_name = _normalize_config_name(str(payload["config_name"]))
        output_path = self.run_configs_dir / config_name

        dataset_catalog_id = str(payload["dataset_catalog_id"])
        self._ensure_dataset_catalog_exists(dataset_catalog_id)

        signal_pack_name = self._ensure_option_allowed(
            category="signal_packs",
            option_id=str(payload["signal_pack_name"]),
        )
        genome_schema_name = self._ensure_option_allowed(
            category="genome_schemas",
            option_id=str(payload["genome_schema_name"]),
        )
        mutation_profile_name = self._ensure_option_allowed(
            category="mutation_profiles",
            option_id=str(payload["mutation_profile_name"]),
        )
        decision_policy_name = self._ensure_option_allowed(
            category="decision_policies",
            option_id=str(payload["decision_policy_name"]),
        )

        seed_mode = str(payload.get("seed_mode") or "range")
        explicit_seeds = _parse_explicit_seeds(payload.get("explicit_seeds"))
        seed_start = (
            int(payload["seed_start"])
            if payload.get("seed_start") is not None
            else None
        )
        seed_count = (
            int(payload["seed_count"])
            if payload.get("seed_count") is not None
            else None
        )

        merged_config = dict(base_config)
        merged_config["dataset_catalog_id"] = dataset_catalog_id
        merged_config["signal_pack_name"] = signal_pack_name
        merged_config["genome_schema_name"] = genome_schema_name
        merged_config["mutation_profile_name"] = mutation_profile_name
        merged_config["decision_policy_name"] = decision_policy_name

        if seed_mode == "explicit":
            if not explicit_seeds:
                raise ValueError("Explicit seed mode requires at least one seed.")
            merged_config["seeds"] = list(explicit_seeds)
            merged_config.pop("seed_start", None)
            merged_config.pop("seed_count", None)
        else:
            if seed_start is None or seed_count is None:
                raise ValueError("Range seed mode requires seed_start and seed_count.")
            merged_config["seed_start"] = seed_start
            merged_config["seed_count"] = seed_count
            merged_config.pop("seeds", None)

        if output_path.exists():
            existing_payload = json.loads(output_path.read_text(encoding="utf-8"))
            if _canonicalize_json_payload(existing_payload) != _canonicalize_json_payload(
                merged_config
            ):
                raise ValueError(
                    "Run config name already exists with different content. "
                    "Choose a different config name instead of overwriting it."
                )

        self.run_configs_dir.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            output_path.write_text(
                json.dumps(merged_config, indent=2) + "\n",
                encoding="utf-8",
            )

        warnings = tuple(
            self._selection_warnings(
                signal_pack_name=signal_pack_name,
                genome_schema_name=genome_schema_name,
                mutation_profile_name=mutation_profile_name,
                decision_policy_name=decision_policy_name,
            )
        )
        return SavedRunConfigResult(
            config_name=output_path.name,
            config_path=str(output_path.relative_to(self.repo_root).as_posix()),
            config_payload=merged_config,
            warnings=warnings,
        )

    def save_mutation_profile_asset(
        self,
        payload: dict[str, Any],
    ) -> SavedMutationProfileAssetResult:
        asset_id = _normalize_asset_id(str(payload["id"]))
        description = _normalize_optional_description(payload.get("description"))
        profile_payload = {
            "strong_mutation_probability": float(payload["strong_mutation_probability"]),
            "numeric_delta_scale": float(payload["numeric_delta_scale"]),
            "flag_flip_probability": float(payload["flag_flip_probability"]),
            "weight_delta": float(payload["weight_delta"]),
            "window_step_mode": str(payload["window_step_mode"]),
        }
        asset_payload = {
            "id": asset_id,
            "description": description,
            "profile": profile_payload,
        }

        candidate_path = self.mutation_profile_assets_dir / f"{asset_id}.json"
        relative_asset_path = candidate_path.relative_to(self.repo_root)
        candidate_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_payload = _canonicalize_json_payload(asset_payload)
        wrote_new_file = False
        if candidate_path.exists():
            existing_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            if _canonicalize_json_payload(existing_payload) != serialized_payload:
                raise ValueError(
                    "Mutation profile id already exists with different content. "
                    "Choose a different id instead of overwriting it."
                )
        else:
            candidate_path.write_text(
                json.dumps(asset_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            wrote_new_file = True

        try:
            # Validate through the existing declarative asset loader contract.
            load_declarative_asset(candidate_path, asset_type="mutation_profiles")
        except Exception:
            if wrote_new_file and candidate_path.exists():
                candidate_path.unlink()
            raise

        return SavedMutationProfileAssetResult(
            asset_id=asset_id,
            asset_path=relative_asset_path.as_posix(),
            asset_payload=asset_payload,
        )

    def save_signal_pack_asset(
        self,
        payload: dict[str, Any],
    ) -> SavedSignalPackAssetResult:
        asset_id = _normalize_asset_id(str(payload["id"]))
        description = _normalize_optional_description(payload.get("description"))
        signal_ids = _parse_signal_id_lines(payload.get("signals"))
        if not signal_ids:
            raise ValueError("At least one signal identifier is required.")

        asset_payload = {
            "id": asset_id,
            "description": description,
            "signals": [
                {
                    "signal_id": signal_id,
                    "params": {"source": signal_id},
                }
                for signal_id in signal_ids
            ],
        }

        candidate_path = self.signal_pack_assets_dir / f"{asset_id}.json"
        relative_asset_path = candidate_path.relative_to(self.repo_root)
        candidate_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_payload = _canonicalize_json_payload(asset_payload)
        wrote_new_file = False
        if candidate_path.exists():
            existing_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            if _canonicalize_json_payload(existing_payload) != serialized_payload:
                raise ValueError(
                    "Signal pack id already exists with different content. "
                    "Choose a different id instead of overwriting it."
                )
        else:
            candidate_path.write_text(
                json.dumps(asset_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            wrote_new_file = True

        try:
            load_declarative_asset(candidate_path, asset_type="signal_packs")
        except Exception:
            if wrote_new_file and candidate_path.exists():
                candidate_path.unlink()
            raise

        return SavedSignalPackAssetResult(
            asset_id=asset_id,
            asset_path=relative_asset_path.as_posix(),
            asset_payload=asset_payload,
        )

    def save_genome_schema_asset(
        self,
        payload: dict[str, Any],
    ) -> SavedGenomeSchemaAssetResult:
        asset_id = _normalize_asset_id(str(payload["id"]))
        description = _normalize_optional_description(payload.get("description"))
        gene_catalog = str(payload["gene_catalog"]).strip()
        if not gene_catalog:
            raise ValueError("gene_catalog is required")

        modules_input = payload.get("modules")
        if not isinstance(modules_input, list) or not modules_input:
            raise ValueError("modules must be a non-empty list")

        modules: list[dict[str, Any]] = []
        for module in modules_input:
            if not isinstance(module, dict):
                raise ValueError("modules must contain objects")
            module_name = str(module["name"]).strip()
            gene_type = str(module["gene_type"]).strip()
            required = module["required"]
            if not module_name:
                raise ValueError("Genome schema module name is required")
            if not gene_type:
                raise ValueError("Genome schema module gene_type is required")
            if not isinstance(required, bool):
                raise ValueError("Genome schema module required must be a bool")
            modules.append(
                {
                    "name": module_name,
                    "gene_type": gene_type,
                    "required": required,
                }
            )

        asset_payload = {
            "id": asset_id,
            "description": description,
            "gene_catalog": gene_catalog,
            "modules": modules,
        }

        candidate_path = self.genome_schema_assets_dir / f"{asset_id}.json"
        relative_asset_path = candidate_path.relative_to(self.repo_root)
        candidate_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_payload = _canonicalize_json_payload(asset_payload)
        wrote_new_file = False
        if candidate_path.exists():
            existing_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            if _canonicalize_json_payload(existing_payload) != serialized_payload:
                raise ValueError(
                    "Genome schema id already exists with different content. "
                    "Choose a different id instead of overwriting it."
                )
        else:
            candidate_path.write_text(
                json.dumps(asset_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            wrote_new_file = True

        try:
            load_declarative_asset(candidate_path, asset_type="genome_schemas")
        except Exception:
            if wrote_new_file and candidate_path.exists():
                candidate_path.unlink()
            raise

        return SavedGenomeSchemaAssetResult(
            asset_id=asset_id,
            asset_path=relative_asset_path.as_posix(),
            asset_payload=asset_payload,
        )

    def save_and_execute(self, payload: dict[str, Any]) -> LaunchedRunResult:
        saved_config = self.save_run_config(payload)
        queue_limit = (
            int(payload["queue_concurrency_limit"])
            if payload.get("queue_concurrency_limit") is not None
            else None
        )
        return self.queue_service.submit_run(
            saved_config=saved_config,
            payload=payload,
            queue_concurrency_limit=queue_limit,
        )

    def _list_dataset_catalogs(self) -> tuple[RunLabDatasetCatalogSummary, ...]:
        manifests = []
        for manifest_path in sorted(self.dataset_configs_dir.glob("*.yaml")):
            manifest = parse_manifest(manifest_path)
            symbols = sorted({entry.symbol for entry in manifest.datasets})
            starts = sorted(entry.start for entry in manifest.datasets)
            ends = sorted(entry.end for entry in manifest.datasets)
            split_summary: dict[str, int] = {}
            sample_dataset_ids: dict[str, tuple[str, ...]] = {}
            for layer in sorted({entry.layer for entry in manifest.datasets}):
                layer_entries = [entry for entry in manifest.datasets if entry.layer == layer]
                split_summary[layer] = len(layer_entries)
                sample_dataset_ids[layer] = tuple(entry.id for entry in layer_entries[:2])

            manifests.append(
                RunLabDatasetCatalogSummary(
                    id=manifest.catalog_id,
                    description=manifest.description,
                    market_type=manifest.market_type,
                    timeframe=manifest.timeframe,
                    asset_symbols=tuple(symbols),
                    date_range_start=starts[0],
                    date_range_end=ends[-1],
                    split_summary=split_summary,
                    sample_dataset_ids=sample_dataset_ids,
                    file_path=str(manifest_path.relative_to(self.repo_root).as_posix()),
                )
            )
        return tuple(manifests)

    def _build_runtime_options(self, category: str) -> tuple[RunLabOption, ...]:
        catalog_payload = ExperimentalCatalogApplicationService(
            core_service=self.catalog_service
        ).get_catalog_category_payload(category)
        option_map = _RUN_LAB_OPTION_RULES[category]
        policy_engine_map = self._build_policy_engine_map()
        options: list[RunLabOption] = []
        for item in catalog_payload:
            rule = option_map.get(item["id"])
            if rule is None:
                if category in {"signal_packs", "mutation_profiles"} and item["origin"] == "asset":
                    classification = "active"
                    selectable = True
                    warning = (
                        "Declarative signal pack asset available for explicit selection."
                        if category == "signal_packs"
                        else "Declarative mutation profile asset available for explicit selection."
                    )
                else:
                    classification = "example_only" if item["origin"] == "asset" else "internal_but_needed"
                    selectable = False
                    warning = "Not part of the current main execution path."
            else:
                classification = rule["classification"]
                selectable = bool(rule["selectable"])
                warning = rule.get("warning")

            engine_name = None
            if category == "decision_policies":
                engine_name = _derive_decision_policy_engine_name(
                    item=item,
                    policy_engine_map=policy_engine_map,
                )

            options.append(
                RunLabOption(
                    id=str(item["id"]),
                    label=_humanize_identifier(str(item["id"])),
                    description=item.get("description"),
                    origin=str(item["origin"]),
                    classification=classification,
                    selectable=selectable,
                    warning=warning,
                    file_path=item.get("file_path"),
                    engine_name=engine_name,
                )
            )
        return tuple(
            sorted(
                options,
                key=lambda option: (
                    0 if option.selectable else 1,
                    0 if option.classification == "active" else 1,
                    option.label,
                ),
            )
        )

    def _build_execution_presets(self) -> tuple[RunLabOption, ...]:
        options: list[RunLabOption] = []
        for preset_name in PRESET_REGISTRY.list():
            preset = PRESET_REGISTRY.get(preset_name)
            options.append(
                RunLabOption(
                    id=preset.name,
                    label=_humanize_identifier(preset.name),
                    description=describe_preset(preset.name),
                    origin="runtime",
                    classification="active",
                    selectable=True,
                    warning=None,
                    file_path="src/evo_system/experimentation/presets.py",
                )
            )
        return tuple(options)

    def _build_signal_pack_authoring_metadata(self) -> SignalPackAuthoringMetadata:
        feature_names = get_default_signal_pack().feature_names
        signal_options = tuple(
            SignalAuthoringOption(id=feature_name)
            for feature_name in feature_names
        )
        return SignalPackAuthoringMetadata(signal_options=signal_options)

    def _build_genome_schema_authoring_metadata(self) -> GenomeSchemaAuthoringMetadata:
        gene_catalog = get_gene_catalog("modular_genome_v1_gene_catalog")
        gene_catalog_options = (
            GenomeSchemaAuthoringOption(id=gene_catalog.name),
        )
        gene_type_options = tuple(
            GenomeSchemaAuthoringOption(id=definition.name)
            for definition in gene_catalog.describe_gene_types()
        )
        suggested_modules = tuple(
            GenomeSchemaSuggestedModule(
                name=slot.name,
                gene_type=slot.name,
                required=slot.required,
            )
            for slot in gene_catalog.describe_schema_slots()
        )
        return GenomeSchemaAuthoringMetadata(
            gene_catalog_options=gene_catalog_options,
            gene_type_options=gene_type_options,
            suggested_modules=suggested_modules,
        )

    def _list_config_templates(self) -> tuple[RunLabTemplateSummary, ...]:
        templates: list[RunLabTemplateSummary] = []
        for config_path in sorted(self.run_configs_dir.glob("*.json")):
            config_json = json.loads(config_path.read_text(encoding="utf-8"))
            snapshot = build_experimental_space_snapshot_from_config_snapshot(config_json)
            explicit_seeds = tuple(int(seed) for seed in config_json.get("seeds", []))
            seed_mode = "explicit" if explicit_seeds else "range"
            templates.append(
                RunLabTemplateSummary(
                    id=config_path.name,
                    label=_humanize_identifier(config_path.stem),
                    file_path=str(config_path.relative_to(self.repo_root).as_posix()),
                    dataset_catalog_id=str(config_json["dataset_catalog_id"]),
                    signal_pack_name=snapshot.signal_pack_name,
                    genome_schema_name=snapshot.genome_schema_name,
                    decision_policy_name=snapshot.decision_policy_name,
                    mutation_profile_name=snapshot.mutation_profile_name,
                    seed_mode=seed_mode,
                    seed_start=(
                        int(config_json["seed_start"])
                        if config_json.get("seed_start") is not None
                        else None
                    ),
                    seed_count=(
                        int(config_json["seed_count"])
                        if config_json.get("seed_count") is not None
                        else None
                    ),
                    explicit_seeds=explicit_seeds,
                    generations_planned=int(config_json["generations_planned"]),
                )
            )
        return tuple(templates)

    def _select_default_template(
        self,
        templates: tuple[RunLabTemplateSummary, ...],
    ) -> RunLabTemplateSummary:
        if not templates:
            raise ValueError("Run Lab requires at least one active config template.")
        for template in templates:
            if "baseline" in template.id.lower():
                return template
        return templates[0]

    def _select_default_execution_preset(
        self,
        presets: tuple[RunLabOption, ...],
    ) -> RunLabOption:
        for preset in presets:
            if preset.id == DEFAULT_EXECUTION_PRESET:
                return preset
        return presets[0]

    def _build_policy_engine_map(self) -> dict[str, str]:
        engine_map: dict[str, str] = {}
        for entry in self.catalog_service.list_policy_engines():
            if entry.payload is None:
                continue
            decision_policy_name = entry.payload.get("builds_decision_policy")
            if isinstance(decision_policy_name, str):
                engine_map[decision_policy_name] = entry.id
        return engine_map

    def _resolve_template_path(self, template_config_name: str) -> Path:
        path = self.run_configs_dir / template_config_name
        if not path.exists():
            raise ValueError(f"Unknown template config: {template_config_name}")
        return path

    def _ensure_dataset_catalog_exists(self, dataset_catalog_id: str) -> None:
        catalog_ids = {catalog.id for catalog in self._list_dataset_catalogs()}
        if dataset_catalog_id not in catalog_ids:
            raise ValueError(f"Unknown dataset catalog: {dataset_catalog_id}")

    def _ensure_option_allowed(self, *, category: str, option_id: str) -> str:
        options = {option.id: option for option in self._build_runtime_options(category)}
        option = options.get(option_id)
        if option is None:
            raise ValueError(f"Unknown {category} option: {option_id}")
        if not option.selectable:
            raise ValueError(
                f"Run Lab does not allow selecting non-runtime {category} option: {option_id}"
            )
        return option.id

    def _selection_warnings(
        self,
        *,
        signal_pack_name: str,
        genome_schema_name: str,
        mutation_profile_name: str,
        decision_policy_name: str,
    ) -> list[str]:
        warnings: list[str] = []
        for category, option_id in (
            ("signal_packs", signal_pack_name),
            ("genome_schemas", genome_schema_name),
            ("mutation_profiles", mutation_profile_name),
            ("decision_policies", decision_policy_name),
        ):
            options = {option.id: option for option in self._build_runtime_options(category)}
            option = options[option_id]
            if option.warning:
                warnings.append(f"{option.label}: {option.warning}")
        return warnings


def _parse_explicit_seeds(value: Any) -> tuple[int, ...]:
    if value in {None, ""}:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return tuple(int(part) for part in parts)
    if isinstance(value, list):
        return tuple(int(part) for part in value)
    raise ValueError("explicit_seeds must be a comma-separated string or list of ints")


def _parse_signal_id_lines(value: Any) -> tuple[str, ...]:
    if value in {None, ""}:
        return ()
    if isinstance(value, str):
        return tuple(
            line.strip()
            for line in value.splitlines()
            if line.strip()
        )
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("signals must be a list of non-empty strings")
            normalized.append(item.strip())
        return tuple(normalized)
    raise ValueError("signals must be a newline-separated string or list of strings")


def _normalize_config_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("config_name is required")
    if any(separator in stripped for separator in ("/", "\\")):
        raise ValueError("config_name must be a simple file name, not a path")
    if not stripped.endswith(".json"):
        stripped = f"{stripped}.json"
    return stripped


def _normalize_asset_id(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("id is required")
    if any(separator in stripped for separator in ("/", "\\")):
        raise ValueError("id must be a simple identifier, not a path")
    if stripped.lower().endswith(".json"):
        stripped = stripped[:-5]
    return stripped


def _normalize_optional_description(value: Any) -> str:
    if value is None:
        return ""
    description = str(value).strip()
    return description


def _humanize_identifier(value: str) -> str:
    return " ".join(
        word.capitalize() for word in re.sub(r"[_\-]+", " ", value).split() if word
    )


def _derive_decision_policy_engine_name(
    *,
    item: dict[str, Any],
    policy_engine_map: dict[str, str],
) -> str | None:
    payload = item.get("payload")
    if isinstance(payload, dict):
        explicit_engine = payload.get("engine")
        if isinstance(explicit_engine, str):
            return explicit_engine
    return policy_engine_map.get(str(item["id"]))


_RUN_LAB_OPTION_RULES: dict[str, dict[str, dict[str, Any]]] = {
    "signal_packs": {
        "policy_v21_default": {
            "classification": "active",
            "selectable": True,
            "warning": None,
        },
        "core_policy_v21_signals_v1": {
            "classification": "example_only",
            "selectable": False,
            "warning": "Reference asset only. It is not part of the current executable runtime path.",
        },
    },
    "genome_schemas": {
        "policy_v2_default": {
            "classification": "legacy_but_still_required",
            "selectable": True,
            "warning": "Compatibility-backed runtime schema kept for the current canonical execution lane.",
        },
        "modular_genome_v1": {
            "classification": "active",
            "selectable": True,
            "warning": None,
        },
        "modular_policy_v2_schema_v1": {
            "classification": "example_only",
            "selectable": False,
            "warning": "Reference schema asset only. It does not define the current executable runtime by itself.",
        },
    },
    "mutation_profiles": {
        "default_runtime_profile": {
            "classification": "legacy_but_still_required",
            "selectable": True,
            "warning": "Current executable mutation profile is still resolved through a compatibility-backed runtime adapter.",
        },
        "balanced_runtime_profile_v1": {
            "classification": "example_only",
            "selectable": False,
            "warning": "Reference mutation asset only. It does not replace the active runtime mutation path.",
        },
    },
    "decision_policies": {
        "policy_v2_default": {
            "classification": "active",
            "selectable": True,
            "warning": None,
        },
        "weighted_policy_v2_v1": {
            "classification": "example_only",
            "selectable": False,
            "warning": "Reference policy asset only. It is not the current executable runtime policy.",
        },
    },
}
