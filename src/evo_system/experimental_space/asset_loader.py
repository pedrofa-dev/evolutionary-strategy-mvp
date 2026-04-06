from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


ASSETS_ROOT = Path(__file__).with_name("assets")
ASSET_DIRECTORY_NAMES = {
    "signal_packs": "signal_packs",
    "gene_catalogs": "gene_catalogs",
    "genome_schemas": "genome_schemas",
    "decision_policies": "decision_policies",
    "mutation_profiles": "mutation_profiles",
    "experiment_presets": "experiment_presets",
}
ASSET_FILE_SUFFIX = ".json"


@dataclass(frozen=True)
class LoadedPluginModule:
    """Imported Python plugin module reference.

    Why it exists:
    - Future plugin discovery should distinguish imported code modules from
      declarative assets loaded from disk.
    - Keeping this as a small DTO avoids leaking importlib details across the
      rest of the codebase.
    """

    module_name: str
    module: ModuleType


@dataclass(frozen=True)
class DeclarativeAsset:
    """Loaded declarative asset from disk.

    This phase intentionally supports JSON only because the repository already
    uses JSON for configs and snapshots, and we do not want to add a YAML
    dependency before the asset format stabilizes.

    ``name`` stores the canonical asset identifier resolved from ``id`` first
    and ``name`` second for backward compatibility with earlier loader tests.
    """

    asset_type: str
    name: str
    path: Path
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_type": self.asset_type,
            "name": self.name,
            "path": self.path.as_posix(),
            "payload": dict(self.payload),
        }


def ensure_asset_directories(root: Path = ASSETS_ROOT) -> dict[str, Path]:
    """Bootstrap helper that creates the expected asset directory layout."""
    directories: dict[str, Path] = {}
    for asset_type, dirname in ASSET_DIRECTORY_NAMES.items():
        directory = root / dirname
        directory.mkdir(parents=True, exist_ok=True)
        directories[asset_type] = directory
    return directories


def load_plugin_module(module_name: str) -> LoadedPluginModule:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ModuleNotFoundError(
                f"Could not import plugin module: {module_name}"
            ) from exc
        raise
    return LoadedPluginModule(module_name=module_name, module=module)


def load_plugin_modules(module_names: Iterable[str]) -> list[LoadedPluginModule]:
    return [load_plugin_module(module_name) for module_name in module_names]


def load_declarative_asset(
    asset_path: Path,
    *,
    asset_type: str,
) -> DeclarativeAsset:
    try:
        payload = json.loads(asset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON asset: {asset_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Asset must contain a JSON object: {asset_path}")

    name = _resolve_asset_identifier(payload, asset_path)
    _validate_asset_payload(payload, asset_type=asset_type, asset_path=asset_path)

    return DeclarativeAsset(
        asset_type=asset_type,
        name=name,
        path=asset_path,
        payload=payload,
    )


def load_declarative_assets(
    asset_dir: Path,
    *,
    asset_type: str,
) -> list[DeclarativeAsset]:
    return [
        load_declarative_asset(asset_path, asset_type=asset_type)
        for asset_path in sorted(asset_dir.glob(f"*{ASSET_FILE_SUFFIX}"))
    ]


def load_all_declarative_assets(
    root: Path = ASSETS_ROOT,
    *,
    validate_references: bool = False,
) -> dict[str, list[DeclarativeAsset]]:
    directories = {
        asset_type: root / dirname
        for asset_type, dirname in ASSET_DIRECTORY_NAMES.items()
    }
    assets = {
        asset_type: load_declarative_assets(asset_dir, asset_type=asset_type)
        for asset_type, asset_dir in directories.items()
    }
    if validate_references:
        validate_declarative_asset_references(assets)
    return assets


def validate_declarative_asset_references(
    assets: dict[str, list[DeclarativeAsset]],
) -> None:
    available_names = {
        asset_type: {asset.name for asset in asset_group}
        for asset_type, asset_group in assets.items()
    }

    for preset in assets.get("experiment_presets", []):
        payload = preset.payload
        for field_name, asset_type in (
            ("signal_pack", "signal_packs"),
            ("genome_schema", "genome_schemas"),
            ("decision_policy", "decision_policies"),
            ("mutation_profile", "mutation_profiles"),
        ):
            reference = payload.get(field_name)
            if reference not in available_names.get(asset_type, set()):
                raise ValueError(
                    f"Unknown {field_name!r} reference {reference!r} in asset: "
                    f"{preset.path}"
                )


def _resolve_asset_identifier(payload: dict[str, Any], asset_path: Path) -> str:
    identifier = payload.get("id")
    if isinstance(identifier, str) and identifier.strip():
        return identifier

    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name

    raise ValueError(
        f"Asset must define a non-empty string 'id' or legacy 'name': {asset_path}"
    )


def _validate_asset_payload(
    payload: dict[str, Any],
    *,
    asset_type: str,
    asset_path: Path,
) -> None:
    validator = _ASSET_VALIDATORS.get(asset_type)
    if validator is None:
        return
    validator(payload, asset_path)


def _validate_signal_pack_asset(payload: dict[str, Any], asset_path: Path) -> None:
    signals = _require_list(payload, "signals", asset_path)
    if not signals:
        raise ValueError(f"Signal pack asset must define at least one signal: {asset_path}")
    for signal in signals:
        if not isinstance(signal, dict):
            raise ValueError(f"Signal definitions must be JSON objects: {asset_path}")
        _require_string(signal, "signal_id", asset_path)
        _optional_string(signal, "alias", asset_path)
        _optional_dict(signal, "params", asset_path)


def _validate_genome_schema_asset(payload: dict[str, Any], asset_path: Path) -> None:
    gene_catalog_name = _require_string(payload, "gene_catalog", asset_path)
    modules = _require_list(payload, "modules", asset_path)
    if not modules:
        raise ValueError(f"Genome schema asset must define at least one module: {asset_path}")
    try:
        from evo_system.experimental_space.gene_catalog import get_gene_catalog

        gene_catalog = get_gene_catalog(gene_catalog_name)
    except KeyError as exc:
        raise ValueError(
            f"Unknown gene_catalog {gene_catalog_name!r} in genome schema asset: "
            f"{asset_path}"
        ) from exc

    allowed_gene_types = set(gene_catalog.list_gene_type_names())
    schema_slots = {slot.name: slot for slot in gene_catalog.describe_schema_slots()}
    expected_module_order = tuple(schema_slots)
    seen_module_names: set[str] = set()
    resolved_module_names: list[str] = []

    for module in modules:
        if not isinstance(module, dict):
            raise ValueError(f"Genome schema modules must be JSON objects: {asset_path}")
        module_name = _require_string(module, "name", asset_path)
        gene_type_name = _require_string(module, "gene_type", asset_path)
        required = _require_bool(module, "required", asset_path)

        if module_name in seen_module_names:
            raise ValueError(
                f"Genome schema asset defines duplicate module {module_name!r}: "
                f"{asset_path}"
            )
        seen_module_names.add(module_name)
        resolved_module_names.append(module_name)

        if module_name not in schema_slots:
            raise ValueError(
                f"Unknown genome schema module {module_name!r} for gene catalog "
                f"{gene_catalog_name!r}: {asset_path}"
            )

        if gene_type_name not in allowed_gene_types:
            raise ValueError(
                f"Unknown gene_type {gene_type_name!r} for gene catalog "
                f"{gene_catalog_name!r}: {asset_path}"
            )

        slot = schema_slots[module_name]
        if required is not slot.required:
            raise ValueError(
                f"Genome schema module {module_name!r} must use required="
                f"{slot.required!r} for gene catalog {gene_catalog_name!r}: "
                f"{asset_path}"
            )

        if gene_type_name != module_name:
            raise ValueError(
                f"Genome schema module {module_name!r} must use matching gene_type "
                f"{module_name!r} for gene catalog {gene_catalog_name!r}: "
                f"{asset_path}"
            )

    if tuple(resolved_module_names) != expected_module_order:
        raise ValueError(
            f"Genome schema modules must match the runtime slot order "
            f"{list(expected_module_order)!r} for gene catalog {gene_catalog_name!r}: "
            f"{asset_path}"
        )


def _validate_decision_policy_asset(payload: dict[str, Any], asset_path: Path) -> None:
    _require_string(payload, "engine", asset_path)
    entry = _require_dict(payload, "entry", asset_path)
    exit_payload = _require_dict(payload, "exit", asset_path)
    _require_string(entry, "trigger_gene", asset_path)
    signals = _require_list(entry, "signals", asset_path)
    for signal in signals:
        if not isinstance(signal, dict):
            raise ValueError(f"Decision policy signal mappings must be objects: {asset_path}")
        _require_string(signal, "signal", asset_path)
        _require_string(signal, "weight_gene_field", asset_path)
    _require_string(exit_payload, "policy_gene", asset_path)
    _require_string(exit_payload, "trade_control_gene", asset_path)


def _validate_mutation_profile_asset(
    payload: dict[str, Any],
    asset_path: Path,
) -> None:
    profile = _require_dict(payload, "profile", asset_path)
    for field_name in (
        "strong_mutation_probability",
        "numeric_delta_scale",
        "flag_flip_probability",
        "weight_delta",
    ):
        _require_number(profile, field_name, asset_path)
    _require_string(profile, "window_step_mode", asset_path)


def _validate_experiment_preset_asset(
    payload: dict[str, Any],
    asset_path: Path,
) -> None:
    for field_name in (
        "signal_pack",
        "genome_schema",
        "decision_policy",
        "mutation_profile",
    ):
        _require_string(payload, field_name, asset_path)
    dataset = _require_dict(payload, "dataset", asset_path)
    _require_string(dataset, "asset", asset_path)
    _require_string(dataset, "timeframe", asset_path)


def _require_string(payload: dict[str, Any], field_name: str, asset_path: Path) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Asset must define a non-empty string {field_name!r}: {asset_path}"
        )
    return value


def _optional_string(payload: dict[str, Any], field_name: str, asset_path: Path) -> None:
    value = payload.get(field_name)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(
            f"Asset field {field_name!r} must be a non-empty string when present: "
            f"{asset_path}"
        )


def _require_dict(payload: dict[str, Any], field_name: str, asset_path: Path) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"Asset field {field_name!r} must be a JSON object: {asset_path}")
    return value


def _optional_dict(payload: dict[str, Any], field_name: str, asset_path: Path) -> None:
    value = payload.get(field_name)
    if value is not None and not isinstance(value, dict):
        raise ValueError(f"Asset field {field_name!r} must be a JSON object: {asset_path}")


def _require_list(payload: dict[str, Any], field_name: str, asset_path: Path) -> list[Any]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"Asset field {field_name!r} must be a JSON array: {asset_path}")
    return value


def _require_bool(payload: dict[str, Any], field_name: str, asset_path: Path) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"Asset field {field_name!r} must be a boolean: {asset_path}")
    return value


def _require_number(payload: dict[str, Any], field_name: str, asset_path: Path) -> float | int:
    value = payload.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Asset field {field_name!r} must be numeric: {asset_path}")
    return value


_ASSET_VALIDATORS = {
    "signal_packs": _validate_signal_pack_asset,
    "genome_schemas": _validate_genome_schema_asset,
    "decision_policies": _validate_decision_policy_asset,
    "mutation_profiles": _validate_mutation_profile_asset,
    "experiment_presets": _validate_experiment_preset_asset,
}
