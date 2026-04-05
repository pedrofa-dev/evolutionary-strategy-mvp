from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from evo_system.champions.classifier import count_positive_and_negative_datasets
from evo_system.champions.metrics import format_dataset_path
from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.experimentation.external_validation import run_external_validation
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    resolve_dataset_root,
)
from evo_system.reporting.report_builder import export_flat_csv
from evo_system.storage import (
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
)
from evo_system.storage.persistence_store import serialize_json, sha256_hex


DEFAULT_DB_PATH = DEFAULT_PERSISTENCE_DB_PATH
DEFAULT_OUTPUT_ROOT = Path("artifacts/analysis")

def ensure_output_dir(output_dir: Path | None) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    auto_dir = DEFAULT_OUTPUT_ROOT / f"reevaluated_champions_{timestamp}"
    auto_dir.mkdir(parents=True, exist_ok=True)
    return auto_dir


def resolve_dataset_paths(
    dataset_dir: Path | None,
    fail_on_missing_datasets: bool,
) -> list[Path]:
    if dataset_dir is None:
        return []

    if not dataset_dir.exists():
        if fail_on_missing_datasets:
            raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
        print(f"WARNING: dataset directory not found, skipping -> {dataset_dir}")
        return []

    dataset_paths = sorted(dataset_dir.rglob("*.csv"))
    if dataset_paths:
        return dataset_paths

    if fail_on_missing_datasets:
        raise ValueError(f"No CSV datasets found under: {dataset_dir}")

    print(f"WARNING: no CSV datasets found, skipping -> {dataset_dir}")
    return []


def resolve_catalog_dataset_paths(
    dataset_root: Path,
    dataset_catalog_id: str,
    dataset_layer: str,
    fail_on_missing_datasets: bool,
) -> list[Path]:
    effective_dataset_root = resolve_dataset_root(dataset_root)
    catalog_root = effective_dataset_root / dataset_catalog_id / dataset_layer
    dataset_paths = sorted(catalog_root.rglob("candles.csv"))
    if dataset_paths:
        return dataset_paths

    if fail_on_missing_datasets:
        raise FileNotFoundError(f"No {dataset_layer} datasets found under {catalog_root}")

    print(f"WARNING: no {dataset_layer} datasets found, skipping -> {catalog_root}")
    return []


def resolve_evaluation_dataset_source(
    dataset_dir: Path | None,
    dataset_root: Path | None,
    dataset_catalog_id: str | None,
    dataset_layer: str,
    fail_on_missing_datasets: bool,
) -> dict[str, Any]:
    if dataset_dir is not None:
        return {
            "source_type": "directory",
            "dataset_catalog_id": None,
            "dataset_root": dataset_dir,
            "dataset_paths": resolve_dataset_paths(
                dataset_dir,
                fail_on_missing_datasets=fail_on_missing_datasets,
            ),
        }

    if dataset_catalog_id is None:
        return {
            "source_type": None,
            "dataset_catalog_id": None,
            "dataset_root": None,
            "dataset_paths": [],
        }

    requested_dataset_root = dataset_root or DEFAULT_DATASET_ROOT
    effective_dataset_root = resolve_dataset_root(requested_dataset_root)

    return {
        "source_type": "catalog",
        "dataset_catalog_id": dataset_catalog_id,
        "dataset_root": effective_dataset_root,
        "dataset_paths": resolve_catalog_dataset_paths(
            dataset_root=requested_dataset_root,
            dataset_catalog_id=dataset_catalog_id,
            dataset_layer=dataset_layer,
            fail_on_missing_datasets=fail_on_missing_datasets,
        ),
    }


def resolve_reevaluation_sources(
    *,
    dataset_root: Path | None,
    external_validation_dir: Path | None,
    external_dataset_catalog_id: str | None,
    audit_dir: Path | None,
    audit_dataset_catalog_id: str | None,
    fail_on_missing_datasets: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    external_source = resolve_evaluation_dataset_source(
        dataset_dir=external_validation_dir,
        dataset_root=dataset_root,
        dataset_catalog_id=external_dataset_catalog_id,
        dataset_layer="external",
        fail_on_missing_datasets=fail_on_missing_datasets,
    )
    audit_source = resolve_evaluation_dataset_source(
        dataset_dir=audit_dir,
        dataset_root=dataset_root,
        dataset_catalog_id=audit_dataset_catalog_id,
        dataset_layer="audit",
        fail_on_missing_datasets=fail_on_missing_datasets,
    )
    return external_source, audit_source


def filter_champions(
    champions: list[dict[str, Any]],
    config_name: str | None = None,
    run_id: str | None = None,
    run_ids: list[str] | None = None,
    champion_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    filtered = champions

    if run_ids is not None:
        allowed_run_ids = set(run_ids)
        filtered = [
            champion
            for champion in filtered
            if champion.get("run_id") in allowed_run_ids
        ]

    if config_name is not None:
        filtered = [
            champion
            for champion in filtered
            if champion.get("config_name") == config_name
        ]

    if run_id is not None:
        filtered = [
            champion
            for champion in filtered
            if champion.get("run_id") == run_id
        ]

    if champion_type is not None:
        filtered = [
            champion
            for champion in filtered
            if champion.get("champion_type") == champion_type
            or champion.get("metrics", {}).get("champion_type") == champion_type
        ]

    filtered = sorted(filtered, key=lambda champion: int(champion["id"]))

    if limit is not None:
        filtered = filtered[:limit]

    return filtered


def build_persisted_champion_metrics(champion_row: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(champion_row.get("champion_metrics_json") or {})
    train_metrics = champion_row.get("train_metrics_json") or {}
    validation_metrics = champion_row.get("validation_metrics_json") or {}

    metrics.setdefault("champion_type", champion_row.get("champion_type"))
    metrics.setdefault("dataset_signature", champion_row.get("dataset_signature"))
    metrics.setdefault("config_name", champion_row.get("config_name"))

    metrics.setdefault("train_selection", train_metrics.get("selection_score"))
    metrics.setdefault("train_profit", train_metrics.get("median_profit"))
    metrics.setdefault("train_drawdown", train_metrics.get("median_drawdown"))
    metrics.setdefault("train_trades", train_metrics.get("median_trades"))
    metrics.setdefault("train_dataset_scores", train_metrics.get("dataset_scores"))
    metrics.setdefault("train_dataset_profits", train_metrics.get("dataset_profits"))
    metrics.setdefault("train_dataset_drawdowns", train_metrics.get("dataset_drawdowns"))
    metrics.setdefault("train_violations", train_metrics.get("violations"))
    metrics.setdefault("train_is_valid", train_metrics.get("is_valid"))

    metrics.setdefault("validation_selection", validation_metrics.get("selection_score"))
    metrics.setdefault("validation_profit", validation_metrics.get("median_profit"))
    metrics.setdefault("validation_drawdown", validation_metrics.get("median_drawdown"))
    metrics.setdefault("validation_trades", validation_metrics.get("median_trades"))
    metrics.setdefault("validation_dispersion", validation_metrics.get("dispersion"))
    metrics.setdefault("validation_dataset_scores", validation_metrics.get("dataset_scores"))
    metrics.setdefault("validation_dataset_profits", validation_metrics.get("dataset_profits"))
    metrics.setdefault("validation_dataset_drawdowns", validation_metrics.get("dataset_drawdowns"))
    metrics.setdefault("validation_violations", validation_metrics.get("violations"))
    metrics.setdefault("validation_is_valid", validation_metrics.get("is_valid"))
    return metrics


def normalize_persisted_champion(champion_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(champion_row["id"]),
        "run_id": str(champion_row["run_id"]),
        "generation_number": champion_row.get("generation_number"),
        "mutation_seed": champion_row.get("mutation_seed"),
        "config_name": champion_row.get("config_name"),
        "genome": dict(champion_row.get("genome_json_snapshot") or {}),
        "metrics": build_persisted_champion_metrics(champion_row),
        "config_snapshot": dict(champion_row.get("config_json_snapshot") or {}),
        "champion_type": champion_row.get("champion_type"),
        "dataset_catalog_id": champion_row.get("dataset_catalog_id"),
        "dataset_signature": champion_row.get("dataset_signature"),
        "persisted_at": champion_row.get("persisted_at"),
    }


def resolve_champion_config_snapshot(champion: dict[str, Any]) -> dict[str, Any]:
    config_snapshot = champion.get("config_snapshot") or champion.get("config_json_snapshot")
    if isinstance(config_snapshot, dict) and config_snapshot:
        return config_snapshot
    raise ValueError("Config snapshot not available for persisted champion.")


def evaluate_with_config_snapshot(
    *,
    agent: Agent,
    dataset_paths: list[Path],
    config_snapshot: dict[str, Any],
):
    return run_external_validation(
        agent=agent,
        external_dataset_paths=dataset_paths,
        cost_penalty_weight=float(config_snapshot.get("cost_penalty_weight", 0.25)),
        trade_cost_rate=float(config_snapshot.get("trade_cost_rate", 0.0)),
        trade_count_penalty_weight=float(
            config_snapshot.get("trade_count_penalty_weight", 0.0)
        ),
        regime_filter_enabled=bool(config_snapshot.get("regime_filter_enabled", False)),
        min_trend_long_for_entry=float(
            config_snapshot.get("min_trend_long_for_entry", 0.0)
        ),
        min_breakout_for_entry=float(config_snapshot.get("min_breakout_for_entry", 0.0)),
        max_realized_volatility_for_entry=config_snapshot.get(
            "max_realized_volatility_for_entry"
        ),
        market_mode_name=str(config_snapshot.get("market_mode_name", "spot")),
        leverage=float(config_snapshot.get("leverage", 1.0)),
    )


def build_manual_selection_scope(
    champions: list[dict[str, Any]],
    *,
    config_name: str | None,
    run_id: str | None,
    run_ids: list[str] | None,
    champion_type: str | None,
) -> dict[str, Any]:
    return {
        "origin": "manual",
        "run_id": run_id,
        "run_ids": sorted({champion["run_id"] for champion in champions})
        if champions
        else (run_ids or ([] if run_id is None else [run_id])),
        "config_name": config_name,
        "champion_type": champion_type,
        "champion_ids": [int(champion["id"]) for champion in champions],
    }


def build_dataset_set_signature(
    *,
    source_type: str | None,
    dataset_catalog_id: str | None,
    dataset_root: Path | None,
    dataset_set_name: str | None,
    dataset_paths: list[Path],
    evaluation_type: str,
) -> str:
    return sha256_hex(
        serialize_json(
            {
                "evaluation_type": evaluation_type,
                "source_type": source_type,
                "dataset_catalog_id": dataset_catalog_id,
                "dataset_root": str(dataset_root) if dataset_root is not None else None,
                "dataset_set_name": dataset_set_name,
                "dataset_names": [str(path) for path in dataset_paths],
            }
        )
    )


def build_evaluation_summary(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    selection_values = [
        float(row[f"{prefix}_selection"])
        for row in rows
        if row.get(f"{prefix}_selection") is not None
    ]
    profit_values = [
        float(row[f"{prefix}_profit"])
        for row in rows
        if row.get(f"{prefix}_profit") is not None
    ]
    return {
        "rows_generated": len(rows),
        "mean_validation_selection": mean(
            float(row["validation_selection"])
            for row in rows
            if row.get("validation_selection") is not None
        )
        if any(row.get("validation_selection") is not None for row in rows)
        else None,
        "mean_validation_profit": mean(
            float(row["validation_profit"])
            for row in rows
            if row.get("validation_profit") is not None
        )
        if any(row.get("validation_profit") is not None for row in rows)
        else None,
        "mean_post_selection": mean(selection_values) if selection_values else None,
        "mean_post_profit": mean(profit_values) if profit_values else None,
        "positive_profit_count": sum(
            1 for value in profit_values if value > 0.0
        ),
        "valid_count": sum(1 for row in rows if bool(row.get(f"{prefix}_is_valid"))),
    }


def build_evaluation_metrics(
    prefix: str,
    evaluation,
    dataset_paths: list[Path],
    dataset_root: Path,
) -> dict[str, Any]:
    positive_datasets, negative_datasets = count_positive_and_negative_datasets(
        evaluation.dataset_profits
    )

    return {
        f"{prefix}_dataset_names": [
            format_dataset_path(path, dataset_root) for path in dataset_paths
        ],
        f"{prefix}_dataset_count": len(dataset_paths),
        f"{prefix}_selection": evaluation.selection_score,
        f"{prefix}_profit": evaluation.median_profit,
        f"{prefix}_drawdown": evaluation.median_drawdown,
        f"{prefix}_trades": evaluation.median_trades,
        f"{prefix}_dispersion": evaluation.dispersion,
        f"{prefix}_positive_datasets": positive_datasets,
        f"{prefix}_negative_datasets": negative_datasets,
        f"{prefix}_scores": evaluation.dataset_scores,
        f"{prefix}_profits": evaluation.dataset_profits,
        f"{prefix}_drawdowns": evaluation.dataset_drawdowns,
        f"{prefix}_violations": evaluation.violations,
        f"{prefix}_is_valid": evaluation.is_valid,
    }


def summarize_metric(
    rows: list[dict[str, Any]],
    field_name: str,
) -> tuple[float | None, float | None]:
    values = [
        float(row[field_name])
        for row in rows
        if row.get(field_name) is not None
    ]
    if not values:
        return None, None
    return mean(values), median(values)


def count_truthy(rows: list[dict[str, Any]], field_name: str) -> int:
    return sum(1 for row in rows if bool(row.get(field_name)))


def count_positive(rows: list[dict[str, Any]], field_name: str) -> int:
    return sum(1 for row in rows if row.get(field_name) is not None and float(row[field_name]) > 0.0)


def format_top_rows(
    rows: list[dict[str, Any]],
    field_name: str,
    title: str,
) -> list[str]:
    top_rows = sorted(
        [row for row in rows if row.get(field_name) is not None],
        key=lambda row: float(row[field_name]),
        reverse=True,
    )[:10]

    lines = [title]
    if not top_rows:
        lines.append("  No data.")
        lines.append("")
        return lines

    for row in top_rows:
        lines.append(
            f"  champion_id={row['champion_id']} | "
            f"run_id={row['run_id']} | "
            f"config_name={row['config_name']} | "
            f"champion_type={row['champion_type'] or 'unknown'} | "
            f"{field_name}={float(row[field_name]):.6f} | "
            f"validation_selection={float(row.get('validation_selection', 0.0)):.6f}"
        )

    lines.append("")
    return lines


def build_report_lines(
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
    external_evaluations_run: int,
    audit_evaluations_run: int,
) -> list[str]:
    external_profit_mean, external_profit_median = summarize_metric(
        rows,
        "external_validation_profit",
    )
    external_selection_mean, external_selection_median = summarize_metric(
        rows,
        "external_validation_selection",
    )
    audit_profit_mean, audit_profit_median = summarize_metric(rows, "audit_profit")
    audit_selection_mean, audit_selection_median = summarize_metric(
        rows,
        "audit_selection",
    )

    lines = [
        "Persisted champion reevaluation report",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Filters used",
        f"  db_path={filters['db_path']}",
        f"  dataset_root={filters['dataset_root'] or 'none'}",
        f"  config_name={filters['config_name'] or 'none'}",
        f"  run_id={filters['run_id'] or 'none'}",
        f"  run_ids={filters.get('run_ids') or 'none'}",
        f"  reevaluation_run_ids={filters.get('reevaluation_run_ids') or 'none'}",
        f"  champion_type={filters['champion_type'] or 'none'}",
        f"  limit={filters['limit'] if filters['limit'] is not None else 'none'}",
        f"  external_validation_dir={filters['external_validation_dir'] or 'none'}",
        f"  external_dataset_catalog_id={filters['external_dataset_catalog_id'] or 'none'}",
        f"  external_dataset_root={filters.get('external_dataset_root') or 'none'}",
        f"  audit_dir={filters['audit_dir'] or 'none'}",
        f"  audit_dataset_catalog_id={filters['audit_dataset_catalog_id'] or 'none'}",
        f"  audit_dataset_root={filters.get('audit_dataset_root') or 'none'}",
        "",
        f"Matched champions: {len(rows)}",
        f"Champions matched for reevaluation: {filters.get('matched_champion_count', len(rows))}",
        f"Rows generated: {filters.get('rows_generated', len(rows))}",
        f"External evaluations run: {external_evaluations_run}",
        f"Audit evaluations run: {audit_evaluations_run}",
        "",
        "External summary",
        f"  mean_external_profit={external_profit_mean if external_profit_mean is not None else 'n/a'}",
        f"  median_external_profit={external_profit_median if external_profit_median is not None else 'n/a'}",
        f"  mean_external_selection={external_selection_mean if external_selection_mean is not None else 'n/a'}",
        f"  median_external_selection={external_selection_median if external_selection_median is not None else 'n/a'}",
        f"  champions_with_external_profit_gt_zero={count_positive(rows, 'external_validation_profit')}",
        f"  champions_with_external_valid_true={count_truthy(rows, 'external_validation_is_valid')}",
        "",
    ]

    resolution_warnings = filters.get("resolution_warnings", [])
    if resolution_warnings:
        lines.extend(["Resolution warnings"])
        for warning in resolution_warnings:
            lines.append(f"  {warning}")
        lines.append("")

    for summary_key, label in (
        ("external_scope_summary", "External scope"),
        ("audit_scope_summary", "Audit scope"),
    ):
        scope_summary = filters.get(summary_key)
        if not scope_summary:
            continue
        lines.extend(
            [
                label,
                f"  catalog_scope_mode={scope_summary['catalog_scope_mode']}",
                f"  dataset_root_scope_mode={scope_summary['dataset_root_scope_mode']}",
                f"  catalog_ids={scope_summary['catalog_ids'] or 'none'}",
                f"  dataset_roots={scope_summary['dataset_roots'] or 'none'}",
            ]
        )
        if scope_summary.get("run_mappings"):
            lines.append("  run mappings:")
            for mapping in scope_summary["run_mappings"]:
                lines.append(
                    f"    run_id={mapping['run_id']} -> "
                    f"catalog_id={mapping['dataset_catalog_id'] or 'none'} -> "
                    f"dataset_root={mapping['dataset_root'] or 'none'}"
                )
        if scope_summary.get("fallbacks"):
            lines.append("  dataset resolution fallbacks:")
            for fallback in scope_summary["fallbacks"]:
                lines.append(
                    f"    run_id={fallback['run_id']} | "
                    f"dataset_resolution_fallback_used=true | "
                    f"reason={fallback['reason']}"
                )
        lines.append("")

    skipped_champions = filters.get("skipped_champions", [])
    if skipped_champions:
        lines.extend(["Skipped champions"])
        for skipped in skipped_champions:
            lines.append(
                f"  champion_id={skipped.get('champion_id')} | "
                f"run_id={skipped.get('run_id')} | "
                f"config_name={skipped.get('config_name')} | "
                f"reason={skipped.get('reason')}"
            )
        lines.append("")

    if audit_evaluations_run > 0:
        lines.extend(
            [
                "Audit summary",
                f"  mean_audit_profit={audit_profit_mean if audit_profit_mean is not None else 'n/a'}",
                f"  median_audit_profit={audit_profit_median if audit_profit_median is not None else 'n/a'}",
                f"  mean_audit_selection={audit_selection_mean if audit_selection_mean is not None else 'n/a'}",
                f"  median_audit_selection={audit_selection_median if audit_selection_median is not None else 'n/a'}",
                f"  champions_with_audit_profit_gt_zero={count_positive(rows, 'audit_profit')}",
                f"  champions_with_audit_valid_true={count_truthy(rows, 'audit_is_valid')}",
                "",
            ]
        )

    if external_evaluations_run > 0:
        lines.extend(
            format_top_rows(
                rows,
                "external_validation_selection",
                "Top 10 champions by external_validation_selection",
            )
        )

    if audit_evaluations_run > 0:
        lines.extend(
            format_top_rows(
                rows,
                "audit_selection",
                "Top 10 champions by audit_selection",
            )
        )

    return lines


def build_reevaluation_rows(
    champions: list[dict[str, Any]],
    dataset_root: Path | None = None,
    external_validation_dir: Path | None = None,
    external_dataset_catalog_id: str | None = None,
    audit_dir: Path | None = None,
    audit_dataset_catalog_id: str | None = None,
    external_sources_by_run_id: dict[str, dict[str, Any]] | None = None,
    audit_sources_by_run_id: dict[str, dict[str, Any]] | None = None,
    fail_on_missing_datasets: bool = False,
) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    external_source, audit_source = resolve_reevaluation_sources(
        dataset_root=dataset_root,
        external_validation_dir=external_validation_dir,
        external_dataset_catalog_id=external_dataset_catalog_id,
        audit_dir=audit_dir,
        audit_dataset_catalog_id=audit_dataset_catalog_id,
        fail_on_missing_datasets=fail_on_missing_datasets,
    )

    external_dataset_paths = external_source["dataset_paths"]
    audit_dataset_paths = audit_source["dataset_paths"]

    automatic_external_paths = [
        source_path
        for source in (external_sources_by_run_id or {}).values()
        for source_path in source.get("dataset_paths", [])
    ]
    automatic_audit_paths = [
        source_path
        for source in (audit_sources_by_run_id or {}).values()
        for source_path in source.get("dataset_paths", [])
    ]

    if (
        not external_dataset_paths
        and not audit_dataset_paths
        and not automatic_external_paths
        and not automatic_audit_paths
    ):
        raise ValueError(
            "No datasets available for reevaluation. Provide direct dataset directories and/or external/audit dataset catalog ids."
        )

    rows: list[dict[str, Any]] = []
    skipped_champions: list[dict[str, Any]] = []
    external_rows_count = 0
    audit_rows_count = 0

    for champion in champions:
        try:
            config_snapshot = resolve_champion_config_snapshot(champion)
            metrics = champion.get("metrics", {})
            genome = Genome.from_dict(champion["genome"])
            agent = Agent.create(genome)
            champion_run_id = champion["run_id"]
            champion_external_source = (
                external_source
                if external_source["dataset_paths"]
                else (external_sources_by_run_id or {}).get(
                    champion_run_id,
                    {
                        "source_type": None,
                        "dataset_catalog_id": None,
                        "dataset_root": None,
                        "dataset_paths": [],
                    },
                )
            )
            champion_audit_source = (
                audit_source
                if audit_source["dataset_paths"]
                else (audit_sources_by_run_id or {}).get(
                    champion_run_id,
                    {
                        "source_type": None,
                        "dataset_catalog_id": None,
                        "dataset_root": None,
                        "dataset_paths": [],
                    },
                )
            )
            champion_external_dataset_paths = champion_external_source["dataset_paths"]
            champion_audit_dataset_paths = champion_audit_source["dataset_paths"]

            row: dict[str, Any] = {
                "champion_id": champion["id"],
                "run_id": champion_run_id,
                "generation_number": champion["generation_number"],
                "mutation_seed": champion["mutation_seed"],
                "config_name": champion["config_name"],
                "champion_type": metrics.get("champion_type"),
                "validation_selection": metrics.get("validation_selection"),
                "validation_profit": metrics.get("validation_profit"),
                "validation_drawdown": metrics.get("validation_drawdown"),
                "validation_trades": metrics.get("validation_trades"),
                "selection_gap": metrics.get("selection_gap"),
                "external_source_type": champion_external_source["source_type"],
                "external_dataset_catalog_id": champion_external_source["dataset_catalog_id"],
                "external_dataset_count": len(champion_external_dataset_paths),
                "external_dataset_root": (
                    str(champion_external_source["dataset_root"])
                    if champion_external_source["dataset_root"] is not None
                    else None
                ),
                "external_dataset_set_name": (
                    champion_external_source["dataset_catalog_id"]
                    or (
                        champion_external_source["dataset_root"].name
                        if champion_external_source["dataset_root"] is not None
                        else None
                    )
                ),
                "external_dataset_resolution_fallback_used": bool(
                    champion_external_source.get("dataset_resolution_fallback_used")
                ),
                "external_dataset_resolution_fallback_reason": champion_external_source.get(
                    "dataset_resolution_fallback_reason"
                ),
                "external_evaluation_type": "external",
                "audit_source_type": champion_audit_source["source_type"],
                "audit_dataset_catalog_id": champion_audit_source["dataset_catalog_id"],
                "audit_dataset_count": len(champion_audit_dataset_paths),
                "audit_dataset_root": (
                    str(champion_audit_source["dataset_root"])
                    if champion_audit_source["dataset_root"] is not None
                    else None
                ),
                "audit_dataset_set_name": (
                    champion_audit_source["dataset_catalog_id"]
                    or (
                        champion_audit_source["dataset_root"].name
                        if champion_audit_source["dataset_root"] is not None
                        else None
                    )
                ),
                "audit_dataset_resolution_fallback_used": bool(
                    champion_audit_source.get("dataset_resolution_fallback_used")
                ),
                "audit_dataset_resolution_fallback_reason": champion_audit_source.get(
                    "dataset_resolution_fallback_reason"
                ),
                "audit_evaluation_type": "audit",
            }

            if champion_external_dataset_paths:
                external_evaluation = evaluate_with_config_snapshot(
                    agent=agent,
                    dataset_paths=champion_external_dataset_paths,
                    config_snapshot=config_snapshot,
                )
                row.update(
                    build_evaluation_metrics(
                        "external_validation",
                        external_evaluation,
                        champion_external_dataset_paths,
                        champion_external_source["dataset_root"] or Path("."),
                    )
                )
                external_rows_count += 1

            if champion_audit_dataset_paths:
                audit_evaluation = evaluate_with_config_snapshot(
                    agent=agent,
                    dataset_paths=champion_audit_dataset_paths,
                    config_snapshot=config_snapshot,
                )
                row.update(
                    build_evaluation_metrics(
                        "audit",
                        audit_evaluation,
                        champion_audit_dataset_paths,
                        champion_audit_source["dataset_root"] or Path("."),
                    )
                )
                audit_rows_count += 1

            rows.append(row)
        except Exception as exc:
            skipped_champions.append(
                {
                    "champion_id": champion.get("id"),
                    "run_id": champion.get("run_id"),
                    "config_name": champion.get("config_name"),
                    "reason": str(exc),
                }
            )

    return (
        rows,
        external_rows_count,
        audit_rows_count,
        skipped_champions,
    )


def write_reevaluation_outputs(
    rows: list[dict[str, Any]],
    output_path: Path,
    filters: dict[str, Any],
    external_evaluations_run: int,
    audit_evaluations_run: int,
    *,
    report_name: str = "reevaluation_report.txt",
    json_name: str = "reevaluated_champions.json",
    csv_name: str = "reevaluated_champions.csv",
    include_csv: bool = True,
) -> dict[str, Any]:
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / csv_name if include_csv else None
    json_path = output_path / json_name
    report_path = output_path / report_name
    per_champion_dir = output_path / "champions"

    if csv_path is not None:
        export_flat_csv(rows, csv_path)
    json_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    per_champion_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        champion_json_path = per_champion_dir / f"champion_{row['champion_id']}.json"
        champion_json_path.write_text(
            json.dumps(row, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    report_lines = build_report_lines(
        rows,
        filters=filters,
        external_evaluations_run=external_evaluations_run,
        audit_evaluations_run=audit_evaluations_run,
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "rows": rows,
        "output_dir": output_path,
        "csv_path": csv_path,
        "json_path": json_path,
        "report_path": report_path,
        "per_champion_dir": per_champion_dir,
        "external_evaluations_run": external_evaluations_run,
        "audit_evaluations_run": audit_evaluations_run,
        "rows_generated": len(rows),
        "status": "completed",
    }


def persist_manual_evaluation_result(
    *,
    db_path: Path,
    champions: list[dict[str, Any]],
    result: dict[str, Any],
    filters: dict[str, Any],
    evaluation_type: str,
    source: dict[str, Any],
) -> int | None:
    if result.get("status") != "completed":
        return None

    dataset_paths = source.get("dataset_paths", [])
    if not dataset_paths:
        return None

    prefix = "external_validation" if evaluation_type == "external" else "audit"
    rows = [
        row
        for row in result["rows"]
        if row.get(f"{prefix}_selection") is not None
    ]
    if not rows:
        return None

    store = PersistenceStore(db_path)
    store.initialize()
    evaluation_id = store.save_champion_evaluation(
        champion_evaluation_uid=str(uuid.uuid4()),
        evaluation_type=evaluation_type,
        evaluation_origin="manual",
        champion_count=len(champions),
        dataset_source_type=source.get("source_type") or "unknown",
        dataset_set_name=rows[0].get(
            "external_dataset_set_name" if evaluation_type == "external" else "audit_dataset_set_name"
        )
        or evaluation_type,
        dataset_catalog_id=source.get("dataset_catalog_id"),
        dataset_root=source.get("dataset_root"),
        dataset_signature=build_dataset_set_signature(
            source_type=source.get("source_type"),
            dataset_catalog_id=source.get("dataset_catalog_id"),
            dataset_root=source.get("dataset_root"),
            dataset_set_name=rows[0].get(
                "external_dataset_set_name" if evaluation_type == "external" else "audit_dataset_set_name"
            ),
            dataset_paths=dataset_paths,
            evaluation_type=evaluation_type,
        ),
        selection_scope_json=build_manual_selection_scope(
            champions,
            config_name=filters.get("config_name"),
            run_id=filters.get("run_id"),
            run_ids=filters.get("run_ids"),
            champion_type=filters.get("champion_type"),
        ),
        evaluation_summary_json={
            "rows_generated": result.get("rows_generated", len(rows)),
            "skipped_champions": filters.get("skipped_champions", []),
            "summary": build_evaluation_summary(rows, prefix),
        },
        logic_version=CURRENT_LOGIC_VERSION,
        output_dir_artifact_path=result["output_dir"],
        flat_csv_artifact_path=result["csv_path"],
        json_artifact_path=result["json_path"],
        report_artifact_path=result["report_path"],
        per_champion_dir_artifact_path=result["per_champion_dir"],
    )
    store.add_champion_evaluation_members(
        evaluation_id,
        [int(row["champion_id"]) for row in rows],
    )
    return evaluation_id


def reevaluate_persisted_champions(
    db_path: Path,
    dataset_root: Path | None = None,
    config_name: str | None = None,
    run_id: str | None = None,
    run_ids: list[str] | None = None,
    champion_type: str | None = None,
    external_validation_dir: Path | None = None,
    external_dataset_catalog_id: str | None = None,
    audit_dir: Path | None = None,
    audit_dataset_catalog_id: str | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    fail_on_missing_datasets: bool = False,
) -> dict[str, Any]:
    store = PersistenceStore(db_path)
    store.initialize()

    resolved_run_ids = list(run_ids or [])
    if run_id is not None:
        resolved_run_ids.append(run_id)

    champions = [
        normalize_persisted_champion(champion_row)
        for champion_row in store.load_champions(run_ids=resolved_run_ids or None)
    ]
    matched_champions = filter_champions(
        champions,
        config_name=config_name,
        run_id=run_id,
        run_ids=run_ids,
        champion_type=champion_type,
        limit=limit,
    )

    external_source, audit_source = resolve_reevaluation_sources(
        dataset_root=dataset_root,
        external_validation_dir=external_validation_dir,
        external_dataset_catalog_id=external_dataset_catalog_id,
        audit_dir=audit_dir,
        audit_dataset_catalog_id=audit_dataset_catalog_id,
        fail_on_missing_datasets=fail_on_missing_datasets,
    )

    rows, external_evaluations_run, audit_evaluations_run, skipped_champions = build_reevaluation_rows(
        champions=matched_champions,
        dataset_root=dataset_root,
        external_validation_dir=external_validation_dir,
        external_dataset_catalog_id=external_dataset_catalog_id,
        audit_dir=audit_dir,
        audit_dataset_catalog_id=audit_dataset_catalog_id,
        fail_on_missing_datasets=fail_on_missing_datasets,
    )
    output_path = ensure_output_dir(output_dir)
    filters = {
        "db_path": db_path,
        "dataset_root": dataset_root,
        "config_name": config_name,
        "run_id": run_id,
        "run_ids": run_ids,
        "reevaluation_run_ids": sorted(
            {champion["run_id"] for champion in matched_champions}
        ),
        "champion_type": champion_type,
        "limit": limit,
        "external_validation_dir": external_validation_dir,
        "external_dataset_catalog_id": external_dataset_catalog_id,
        "external_dataset_root": external_source["dataset_root"],
        "audit_dir": audit_dir,
        "audit_dataset_catalog_id": audit_dataset_catalog_id,
        "audit_dataset_root": audit_source["dataset_root"],
        "matched_champion_count": len(matched_champions),
        "rows_generated": len(rows),
        "skipped_champions": skipped_champions,
    }
    result = write_reevaluation_outputs(
        rows,
        output_path=output_path,
        filters=filters,
        external_evaluations_run=external_evaluations_run,
        audit_evaluations_run=audit_evaluations_run,
    )
    result["matched_count"] = len(rows)
    result["external_champion_evaluation_id"] = persist_manual_evaluation_result(
        db_path=db_path,
        champions=matched_champions,
        result=result,
        filters=filters,
        evaluation_type="external",
        source=external_source,
    )
    result["audit_champion_evaluation_id"] = persist_manual_evaluation_result(
        db_path=db_path,
        champions=matched_champions,
        result=result,
        filters=filters,
        evaluation_type="audit",
        source=audit_source,
    )
    return result
