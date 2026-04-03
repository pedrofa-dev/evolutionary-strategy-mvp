from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
import uuid

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.dataset_roots import DEFAULT_DATASET_ROOT
from evo_system.experimentation.persisted_champion_reevaluation import (
    build_reevaluation_rows,
    normalize_persisted_champion,
    resolve_evaluation_dataset_source,
    write_reevaluation_outputs,
)
from evo_system.reporting.decision_support import build_multiseed_decision_payload
from evo_system.reporting.report_builder import analyze_champions
from evo_system.storage import (
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
)
from evo_system.storage.persistence_store import serialize_json, sha256_hex

MULTISEED_QUICK_SUMMARY_NAME = "multiseed_quick_summary.txt"
MULTISEED_CHAMPIONS_SUMMARY_NAME = "multiseed_champions_summary.txt"
ANALYSIS_DIRNAME = "analysis"
DEBUG_DIRNAME = "debug"
CHAMPIONS_ANALYSIS_DIRNAME = "champions_analysis"
POST_MULTISEED_VALIDATION_DIRNAME = "post_multiseed_validation"


@dataclass(frozen=True)
class PostMultiseedAnalysisResult:
    summary_path: Path
    quick_summary_path: Path
    champions_summary_path: Path
    analysis_dir: Path
    debug_dir: Path
    champions_analysis_dir: Path
    external_output_dir: Path
    audit_output_dir: Path
    champion_count: int
    champion_analysis_status: str
    external_evaluation_status: str
    audit_evaluation_status: str
    verdict: str
    recommended_next_action: str


def build_multiseed_quick_summary_lines(
    multiseed_dir: Path,
    dataset_root_label: str,
    decision_payload: dict[str, Any],
) -> list[str]:
    def safe_metric(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        return float(value)

    validation_summary = decision_payload["validation_summary"]
    external_summary = decision_payload["external_summary"]
    audit_summary = decision_payload["audit_summary"]
    best_candidate = decision_payload.get("best_candidate") or {}
    experimental_space_summary = decision_payload.get("experimental_space_summary") or {}
    stack_labels = experimental_space_summary.get("stack_labels") or []

    lines = [
        f"Multiseed: {multiseed_dir.name}",
        (
            "Runs: "
            f"planned={decision_payload['runs_planned']} | "
            f"completed={decision_payload['runs_completed']} | "
            f"executed={decision_payload['runs_executed']} | "
            f"reused={decision_payload['runs_reused']} | "
            f"failed={decision_payload['runs_failed']}"
        ),
        f"Dataset root: {dataset_root_label}",
        (
            "Modules: "
            f"{experimental_space_summary.get('stack_mode', 'unknown')} | "
            f"{stack_labels[0] if stack_labels else 'unknown'}"
        ),
        f"Champions found: {decision_payload['champion_count']}",
        (
            "Best champion: "
            + (
                f"run_id={best_candidate.get('run_id')} | "
                f"config={best_candidate.get('config_name')} | "
                f"validation_selection={safe_metric(best_candidate.get('validation_selection')):.4f} | "
                f"validation_profit={safe_metric(best_candidate.get('validation_profit')):.4f} | "
                f"selection_gap={safe_metric(best_candidate.get('selection_gap')):.4f} | "
                f"dispersion={safe_metric(best_candidate.get('validation_dispersion')):.4f}"
                if best_candidate
                else "none"
            )
        ),
        (
            "Validation profile: "
            f"mean_selection={float(validation_summary.get('mean_validation_selection') or 0.0):.4f} | "
            f"mean_profit={float(validation_summary.get('mean_validation_profit') or 0.0):.4f} | "
            f"mean_abs_selection_gap={float(validation_summary.get('mean_abs_selection_gap') or 0.0):.4f} | "
            f"selection_dispersion={float(validation_summary.get('validation_selection_dispersion') or 0.0):.4f}"
        ),
        (
            "External: "
            f"{external_summary['pass_label']} | "
            f"mean_profit={float(external_summary.get('mean_profit') or 0.0):.4f} | "
            f"valid={external_summary['valid_count']} | "
            f"positive_profit={external_summary['positive_profit_count']}"
        ),
        (
            "Audit: "
            f"{audit_summary['pass_label']} | "
            f"mean_profit={float(audit_summary.get('mean_profit') or 0.0):.4f} | "
            f"valid={audit_summary['valid_count']} | "
            f"positive_profit={audit_summary['positive_profit_count']}"
        ),
        f"Final verdict: {decision_payload['verdict']}",
        f"Likely limit: {decision_payload['likely_limit']}",
        f"Next action: {decision_payload['recommended_next_action']}",
    ]

    if decision_payload["failure_examples"]:
        lines.append(f"Failures: {decision_payload['failure_examples'][0]}")

    return lines


def write_multiseed_quick_summary(
    multiseed_dir: Path,
    dataset_root_label: str,
    decision_payload: dict[str, Any],
) -> Path:
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    quick_summary_path = multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    quick_summary_path.write_text(
        "\n".join(
            build_multiseed_quick_summary_lines(
                multiseed_dir=multiseed_dir,
                dataset_root_label=dataset_root_label,
                decision_payload=decision_payload,
            )
        ),
        encoding="utf-8",
    )
    return quick_summary_path


def load_persisted_multiseed_champions(
    persistence_db_path: Path,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    return [
        normalize_persisted_champion(row)
        for row in store.load_champions(run_ids=run_ids)
    ]


def load_run_execution_contexts(
    persistence_db_path: Path,
    run_ids: list[str],
) -> dict[str, dict[str, Any]]:
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    run_execution_rows = store.load_run_executions(run_ids=run_ids)
    return {
        str(row["run_id"]): row
        for row in run_execution_rows
    }


def resolve_automatic_validation_sources_by_run_id(
    run_execution_contexts: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    external_sources: dict[str, dict[str, Any]] = {}
    audit_sources: dict[str, dict[str, Any]] = {}

    for run_id, context in run_execution_contexts.items():
        dataset_catalog_id = context.get("dataset_catalog_id")
        dataset_context_json = context.get("dataset_context_json") or {}
        persisted_dataset_root = (
            context.get("resolved_dataset_root")
            or context.get("requested_dataset_root")
            or dataset_context_json.get("resolved_dataset_root")
        )
        dataset_resolution_fallback_used = persisted_dataset_root is None
        dataset_resolution_fallback_reason = (
            "missing_persisted_dataset_root_context"
            if dataset_resolution_fallback_used
            else None
        )
        if dataset_resolution_fallback_used:
            print(
                "WARNING: automatic post-multiseed dataset resolution fell back to "
                f"{DEFAULT_DATASET_ROOT} for run_id={run_id} because persisted dataset root context is missing."
            )
        dataset_root = (
            Path(persisted_dataset_root)
            if persisted_dataset_root
            else DEFAULT_DATASET_ROOT
        )

        external_source = resolve_evaluation_dataset_source(
            dataset_dir=None,
            dataset_root=dataset_root,
            dataset_catalog_id=dataset_catalog_id,
            dataset_layer="external",
            fail_on_missing_datasets=False,
        )
        external_source["dataset_resolution_fallback_used"] = dataset_resolution_fallback_used
        external_source["dataset_resolution_fallback_reason"] = dataset_resolution_fallback_reason
        external_source["run_id"] = run_id
        external_sources[run_id] = external_source

        audit_source = resolve_evaluation_dataset_source(
            dataset_dir=None,
            dataset_root=dataset_root,
            dataset_catalog_id=dataset_catalog_id,
            dataset_layer="audit",
            fail_on_missing_datasets=False,
        )
        audit_source["dataset_resolution_fallback_used"] = dataset_resolution_fallback_used
        audit_source["dataset_resolution_fallback_reason"] = dataset_resolution_fallback_reason
        audit_source["run_id"] = run_id
        audit_sources[run_id] = audit_source

    return external_sources, audit_sources


def build_scope_summary(
    sources_by_run_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    catalog_ids = sorted(
        {
            source.get("dataset_catalog_id")
            for source in sources_by_run_id.values()
            if source.get("dataset_catalog_id")
        }
    )
    dataset_roots = sorted(
        {
            str(source.get("dataset_root"))
            for source in sources_by_run_id.values()
            if source.get("dataset_root") is not None
        }
    )
    run_mappings = [
        {
            "run_id": run_id,
            "dataset_catalog_id": source.get("dataset_catalog_id"),
            "dataset_root": (
                str(source.get("dataset_root"))
                if source.get("dataset_root") is not None
                else None
            ),
        }
        for run_id, source in sorted(sources_by_run_id.items())
    ]
    fallbacks = [
        {
            "run_id": run_id,
            "reason": source.get("dataset_resolution_fallback_reason"),
        }
        for run_id, source in sorted(sources_by_run_id.items())
        if source.get("dataset_resolution_fallback_used")
    ]
    return {
        "catalog_scope_mode": "single_catalog" if len(catalog_ids) <= 1 else "mixed_catalogs",
        "dataset_root_scope_mode": "single_root" if len(dataset_roots) <= 1 else "mixed_roots",
        "catalog_ids": catalog_ids,
        "dataset_roots": dataset_roots,
        "run_mappings": run_mappings,
        "fallbacks": fallbacks,
    }


def build_resolution_warnings(
    label: str,
    sources_by_run_id: dict[str, dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    for run_id, source in sorted(sources_by_run_id.items()):
        if source.get("dataset_resolution_fallback_used"):
            warnings.append(
                f"{label}: run_id={run_id} used dataset_resolution_fallback_used=true "
                f"because {source.get('dataset_resolution_fallback_reason')}"
            )
    return warnings


def write_post_multiseed_reevaluation_summary(
    output_dir: Path,
    *,
    external_result: dict[str, Any],
    audit_result: dict[str, Any],
    external_scope_summary: dict[str, Any],
    audit_scope_summary: dict[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "post_multiseed_reevaluation_summary.txt"
    lines = [
        "Post-multiseed reevaluation summary",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        (
            f"External: status={external_result.get('status', 'unknown')} | "
            f"rows_generated={external_result.get('rows_generated', 0)}"
        ),
        (
            f"Audit: status={audit_result.get('status', 'unknown')} | "
            f"rows_generated={audit_result.get('rows_generated', 0)}"
        ),
        "",
        "External scope",
        f"  catalog_scope_mode={external_scope_summary['catalog_scope_mode']}",
        f"  dataset_root_scope_mode={external_scope_summary['dataset_root_scope_mode']}",
        f"  catalog_ids={external_scope_summary['catalog_ids'] or 'none'}",
        f"  dataset_roots={external_scope_summary['dataset_roots'] or 'none'}",
        "",
        "Audit scope",
        f"  catalog_scope_mode={audit_scope_summary['catalog_scope_mode']}",
        f"  dataset_root_scope_mode={audit_scope_summary['dataset_root_scope_mode']}",
        f"  catalog_ids={audit_scope_summary['catalog_ids'] or 'none'}",
        f"  dataset_roots={audit_scope_summary['dataset_roots'] or 'none'}",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def build_champion_selection_scope(
    run_summaries: list[HistoricalRunSummary],
    champion_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "origin": "automatic_post_multiseed",
        "run_ids": [summary.run_id for summary in run_summaries],
        "config_names": sorted({summary.config_name for summary in run_summaries}),
        "champion_ids": [int(row["id"]) for row in champion_rows],
        "champion_run_ids": sorted({row["run_id"] for row in champion_rows}),
    }


def select_matching_champion_ids(
    champion_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[int]:
    row_keys = {
        (
            row.get("run_id"),
            row.get("generation_number"),
            row.get("mutation_seed"),
            row.get("config_name"),
        )
        for row in rows
    }
    champion_ids: list[int] = []
    for champion_row in champion_rows:
        candidate_key = (
            champion_row.get("run_id"),
            champion_row.get("generation_number"),
            champion_row.get("mutation_seed"),
            champion_row.get("config_name"),
        )
        if candidate_key in row_keys:
            champion_ids.append(int(champion_row["id"]))
    return champion_ids


def build_dataset_set_signature(
    *,
    rows: list[dict[str, Any]],
    dataset_prefix: str,
) -> str:
    dataset_names = rows[0].get(f"{dataset_prefix}_dataset_names", []) if rows else []
    source = {
        "evaluation_type": dataset_prefix,
        "source_type": rows[0].get(f"{dataset_prefix}_source_type") if rows else None,
        "dataset_catalog_id": rows[0].get(f"{dataset_prefix}_dataset_catalog_id") if rows else None,
        "dataset_root": rows[0].get(f"{dataset_prefix}_dataset_root") if rows else None,
        "dataset_set_name": rows[0].get(f"{dataset_prefix}_dataset_set_name") if rows else None,
        "dataset_names": dataset_names,
    }
    return sha256_hex(serialize_json(source))


def persist_automatic_champion_analysis(
    *,
    persistence_db_path: Path,
    multiseed_run_id: int,
    run_summaries: list[HistoricalRunSummary],
    champion_rows: list[dict[str, Any]],
    champion_analysis_result: dict[str, Any] | None,
) -> str:
    if not champion_rows:
        return "skipped_no_champions"
    if champion_analysis_result is None:
        return "failed"

    store = PersistenceStore(persistence_db_path)
    store.initialize()
    analysis_id = store.save_champion_analysis(
        champion_analysis_uid=str(uuid.uuid4()),
        multiseed_run_id=multiseed_run_id,
        analysis_type="automatic_post_multiseed",
        champion_count=len(champion_rows),
        selection_scope_json=build_champion_selection_scope(run_summaries, champion_rows),
        analysis_summary_json={
            "champion_count": champion_analysis_result["champion_count"],
            "report_data": champion_analysis_result["report_data"],
            "champion_card": champion_analysis_result["champion_card"],
        },
        logic_version=CURRENT_LOGIC_VERSION,
        output_dir_artifact_path=champion_analysis_result["output_dir"],
        flat_csv_artifact_path=champion_analysis_result["csv_path"],
        report_artifact_path=champion_analysis_result["report_path"],
        patterns_artifact_path=champion_analysis_result["patterns_path"],
        champion_card_artifact_path=champion_analysis_result["champion_card_path"],
    )
    store.add_champion_analysis_members(
        analysis_id,
        [int(row["id"]) for row in champion_rows],
    )
    return "completed"


def persist_automatic_champion_evaluation(
    *,
    persistence_db_path: Path,
    multiseed_run_id: int,
    run_summaries: list[HistoricalRunSummary],
    champion_rows: list[dict[str, Any]],
    evaluation_type: str,
    result: dict[str, Any],
) -> str:
    if not champion_rows:
        return "skipped_no_champions"

    status = result.get("status", "failed")
    if status != "completed":
        return status

    rows = result["rows"]
    if not rows:
        return "failed"

    metrics_prefix = "external_validation" if evaluation_type == "external" else "audit"
    dataset_prefix = "external" if evaluation_type == "external" else "audit"
    dataset_source_keys = {
        (
            row.get(f"{dataset_prefix}_source_type"),
            row.get(f"{dataset_prefix}_dataset_catalog_id"),
            row.get(f"{dataset_prefix}_dataset_root"),
            row.get(f"{dataset_prefix}_dataset_set_name"),
        )
        for row in rows
    }
    if len(dataset_source_keys) == 1:
        dataset_source_type = rows[0].get(f"{dataset_prefix}_source_type") or "unknown"
        dataset_set_name = rows[0].get(f"{dataset_prefix}_dataset_set_name") or evaluation_type
        dataset_catalog_id = rows[0].get(f"{dataset_prefix}_dataset_catalog_id")
        dataset_root = rows[0].get(f"{dataset_prefix}_dataset_root")
    else:
        dataset_source_type = "mixed_catalog_scoped"
        dataset_set_name = f"mixed_{evaluation_type}"
        dataset_catalog_id = None
        dataset_root = None

    evaluation_member_ids = select_matching_champion_ids(champion_rows, rows)
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    evaluation_id = store.save_champion_evaluation(
        champion_evaluation_uid=str(uuid.uuid4()),
        multiseed_run_id=multiseed_run_id,
        evaluation_type=evaluation_type,
        evaluation_origin="automatic_post_multiseed",
        champion_count=len(champion_rows),
        dataset_source_type=dataset_source_type,
        dataset_set_name=dataset_set_name,
        dataset_catalog_id=dataset_catalog_id,
        dataset_root=dataset_root,
        dataset_signature=build_dataset_set_signature(rows=rows, dataset_prefix=dataset_prefix),
        selection_scope_json=build_champion_selection_scope(run_summaries, champion_rows),
        evaluation_summary_json={
            "rows_generated": result.get("rows_generated", len(rows)),
            "external_evaluations_run": result.get("external_evaluations_run", 0),
            "audit_evaluations_run": result.get("audit_evaluations_run", 0),
            "mean_summary": summarize_rows(rows, metrics_prefix),
            "dataset_sources": [
                {
                    "source_type": source_type,
                    "dataset_catalog_id": catalog_id,
                    "dataset_root": dataset_root_value,
                    "dataset_set_name": set_name,
                }
                for source_type, catalog_id, dataset_root_value, set_name in sorted(dataset_source_keys)
            ],
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
        evaluation_member_ids,
    )
    return "completed"


def write_skip_reevaluation(
    output_dir: Path,
    title: str,
    reason: str,
    *,
    status: str,
    report_name: str = "reevaluation_report.txt",
    json_name: str = "reevaluated_champions.json",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / report_name
    json_path = output_dir / json_name
    champions_dir = output_dir / "champions"
    champions_dir.mkdir(parents=True, exist_ok=True)

    report_path.write_text(f"{title}\n\n{reason}\n", encoding="utf-8")
    json_path.write_text("[]", encoding="utf-8")

    return {
        "rows": [],
        "output_dir": output_dir,
        "csv_path": None,
        "json_path": json_path,
        "report_path": report_path,
        "per_champion_dir": champions_dir,
        "external_evaluations_run": 0,
        "audit_evaluations_run": 0,
        "status": status,
    }


def summarize_rows(rows: list[dict[str, Any]], prefix: str) -> dict[str, float | int | None]:
    if not rows:
        return {
            "mean_validation_selection": None,
            "mean_validation_profit": None,
            "mean_post_selection": None,
            "mean_post_profit": None,
            "positive_profit_count": 0,
            "valid_count": 0,
        }

    validation_selection_values = [
        float(row["validation_selection"])
        for row in rows
        if row.get("validation_selection") is not None
    ]
    validation_profit_values = [
        float(row["validation_profit"])
        for row in rows
        if row.get("validation_profit") is not None
    ]
    post_selection_values = [
        float(row[f"{prefix}_selection"])
        for row in rows
        if row.get(f"{prefix}_selection") is not None
    ]
    post_profit_values = [
        float(row[f"{prefix}_profit"])
        for row in rows
        if row.get(f"{prefix}_profit") is not None
    ]

    return {
        "mean_validation_selection": mean(validation_selection_values)
        if validation_selection_values else None,
        "mean_validation_profit": mean(validation_profit_values)
        if validation_profit_values else None,
        "mean_post_selection": mean(post_selection_values) if post_selection_values else None,
        "mean_post_profit": mean(post_profit_values) if post_profit_values else None,
        "positive_profit_count": sum(
            1
            for row in rows
            if row.get(f"{prefix}_profit") is not None
            and float(row[f"{prefix}_profit"]) > 0.0
        ),
        "valid_count": sum(1 for row in rows if bool(row.get(f"{prefix}_is_valid"))),
    }


def build_candidate_lines(rows: list[dict[str, Any]], field_name: str) -> list[str]:
    lines: list[str] = []
    ranked_rows = sorted(
        [row for row in rows if row.get(field_name) is not None],
        key=lambda row: float(row[field_name]),
        reverse=True,
    )[:5]

    if not ranked_rows:
        lines.append("  No data.")
        return lines

    for row in ranked_rows:
        lines.append(
            f"  champion_id={row['champion_id']} | "
            f"run_id={row['run_id']} | "
            f"config_name={row['config_name']} | "
            f"champion_type={row.get('champion_type') or 'unknown'} | "
            f"{field_name}={float(row[field_name]):.4f}"
        )

    return lines


def format_mean_line(summary: dict[str, Any], label: str) -> str:
    return (
        f"  {label}: "
        f"pass={summary['pass_label']} | "
        f"mean_selection={float(summary.get('mean_selection') or 0.0):.4f} | "
        f"mean_profit={float(summary.get('mean_profit') or 0.0):.4f} | "
        f"valid={summary['valid_count']} | "
        f"positive_profit={summary['positive_profit_count']}"
    )


def write_multiseed_champions_summary(
    analysis_dir: Path,
    decision_payload: dict[str, Any],
    champion_analysis_result: dict[str, Any] | None,
    external_result: dict[str, Any],
    audit_result: dict[str, Any],
) -> Path:
    def safe_metric(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        return float(value)

    analysis_dir.mkdir(parents=True, exist_ok=True)
    summary_path = analysis_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
    lines = [
        "Multiseed decision report",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Verdict: {decision_payload['verdict']}",
        f"Likely limit: {decision_payload['likely_limit']}",
        f"Explanation: {decision_payload['explanation']}",
        f"Recommended next action: {decision_payload['recommended_next_action']}",
        "",
        "Execution summary",
        (
            f"  planned={decision_payload['runs_planned']} | "
            f"completed={decision_payload['runs_completed']} | "
            f"executed={decision_payload['runs_executed']} | "
            f"reused={decision_payload['runs_reused']} | "
            f"failed={decision_payload['runs_failed']}"
        ),
        f"  champions_found={decision_payload['champion_count']}",
        (
            "  modules="
            f"{(decision_payload.get('experimental_space_summary') or {}).get('stack_mode', 'unknown')}"
        ),
        "",
        "Active modular components",
    ]

    stack_labels = (
        (decision_payload.get("experimental_space_summary") or {}).get("stack_labels") or []
    )
    if stack_labels:
        for label in stack_labels:
            lines.append(f"  {label}")
    else:
        lines.append("  unknown")

    lines.extend([
        "",
        "Validation interpretation",
        (
            f"  mean_validation_selection={float(decision_payload['validation_summary'].get('mean_validation_selection') or 0.0):.4f} | "
            f"mean_validation_profit={float(decision_payload['validation_summary'].get('mean_validation_profit') or 0.0):.4f} | "
            f"mean_abs_selection_gap={float(decision_payload['validation_summary'].get('mean_abs_selection_gap') or 0.0):.4f} | "
            f"mean_abs_profit_gap={float(decision_payload['validation_summary'].get('mean_abs_profit_gap') or 0.0):.4f} | "
            f"selection_dispersion={float(decision_payload['validation_summary'].get('validation_selection_dispersion') or 0.0):.4f}"
        ),
        "",
        "External and audit interpretation",
        format_mean_line(decision_payload["external_summary"], "external"),
        format_mean_line(decision_payload["audit_summary"], "audit"),
        "",
        "Pattern highlights",
    ])

    pattern_highlights = decision_payload.get("pattern_highlights", [])
    if pattern_highlights:
        for highlight in pattern_highlights:
            lines.append(f"  - {highlight}")
    else:
        lines.append("  - No strong recurrent patterns detected.")

    lines.append("")
    lines.append("Best champion inside this campaign")
    best_candidate = decision_payload.get("best_candidate") or {}
    if best_candidate:
        lines.append(
            f"  run_id={best_candidate.get('run_id')} | "
            f"config={best_candidate.get('config_name')} | "
            f"validation_selection={safe_metric(best_candidate.get('validation_selection')):.4f} | "
            f"validation_profit={safe_metric(best_candidate.get('validation_profit')):.4f} | "
            f"validation_drawdown={safe_metric(best_candidate.get('validation_drawdown')):.4f} | "
            f"validation_trades={safe_metric(best_candidate.get('validation_trades')):.1f} | "
            f"selection_gap={safe_metric(best_candidate.get('selection_gap')):.4f}"
        )
    else:
        lines.append("  No champion candidate survived validation.")

    lines.append("")
    lines.append("Candidate ranking by external selection")
    lines.extend(build_candidate_lines(external_result["rows"], "external_validation_selection"))
    lines.append("")
    lines.append("Candidate ranking by audit selection")
    lines.extend(build_candidate_lines(audit_result["rows"], "audit_selection"))

    if champion_analysis_result is not None:
        lines.append("")
        lines.append("Analysis artifacts")
        lines.append(
            f"  Debug champion analysis directory: {champion_analysis_result['output_dir']}"
        )

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def run_post_execution_validation(
    *,
    champions: list[dict[str, Any]],
    run_summaries: list[HistoricalRunSummary],
    external_validation_dir: Path | None,
    audit_dir: Path | None,
    external_output_dir: Path,
    audit_output_dir: Path,
    automatic_external_sources_by_run_id: dict[str, dict[str, Any]],
    automatic_audit_sources_by_run_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not champions:
        external_result = write_skip_reevaluation(
            external_output_dir,
            "Post-multiseed external validation",
            "No persisted champions were found for this multiseed execution.",
            status="skipped_no_champions",
            report_name="external_reevaluation_report.txt",
            json_name="external_reevaluated_champions.json",
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            "Post-multiseed audit validation",
            "No persisted champions were found for this multiseed execution.",
            status="skipped_no_champions",
            report_name="audit_reevaluation_report.txt",
            json_name="audit_reevaluated_champions.json",
        )
        return external_result, audit_result

    external_requested = (
        external_validation_dir is not None
        or any(source.get("dataset_paths") for source in automatic_external_sources_by_run_id.values())
    )
    if external_validation_dir is not None and external_validation_dir.exists():
        try:
            external_rows, external_count, _, external_skipped = build_reevaluation_rows(
                champions=champions,
                external_validation_dir=external_validation_dir,
            )
            external_result = write_reevaluation_outputs(
                rows=external_rows,
                output_path=external_output_dir,
                filters={
                    "db_path": "automatic_post_multiseed",
                    "dataset_root": None,
                    "config_name": "multiple",
                    "run_id": "multiple",
                    "run_ids": sorted({summary.run_id for summary in run_summaries}),
                    "reevaluation_run_ids": sorted({champion["run_id"] for champion in champions}),
                    "champion_type": None,
                    "limit": None,
                    "external_validation_dir": external_validation_dir,
                    "external_dataset_catalog_id": None,
                    "external_dataset_root": external_validation_dir,
                    "audit_dir": None,
                    "audit_dataset_catalog_id": None,
                    "audit_dataset_root": None,
                    "matched_champion_count": len(champions),
                    "rows_generated": len(external_rows),
                    "skipped_champions": external_skipped,
                    "external_scope_summary": build_scope_summary(automatic_external_sources_by_run_id),
                    "resolution_warnings": build_resolution_warnings(
                        "external",
                        automatic_external_sources_by_run_id,
                    ),
                },
                external_evaluations_run=external_count,
                audit_evaluations_run=0,
                report_name="external_reevaluation_report.txt",
                json_name="external_reevaluated_champions.json",
                include_csv=False,
            )
        except ValueError as exc:
            print(f"WARNING: external multiseed validation skipped -> {exc}")
            external_result = write_skip_reevaluation(
                external_output_dir,
                "Post-multiseed external validation",
                str(exc),
                status="failed",
                report_name="external_reevaluation_report.txt",
                json_name="external_reevaluated_champions.json",
            )
    elif external_validation_dir is None and external_requested:
        try:
            external_rows, external_count, _, external_skipped = build_reevaluation_rows(
                champions=champions,
                external_sources_by_run_id=automatic_external_sources_by_run_id,
            )
            external_result = write_reevaluation_outputs(
                rows=external_rows,
                output_path=external_output_dir,
                filters={
                    "db_path": "automatic_post_multiseed",
                    "dataset_root": None,
                    "config_name": "multiple",
                    "run_id": "multiple",
                    "run_ids": sorted({summary.run_id for summary in run_summaries}),
                    "reevaluation_run_ids": sorted({champion["run_id"] for champion in champions}),
                    "champion_type": None,
                    "limit": None,
                    "external_validation_dir": None,
                    "external_dataset_catalog_id": sorted(
                        {
                            source.get("dataset_catalog_id")
                            for source in automatic_external_sources_by_run_id.values()
                            if source.get("dataset_catalog_id")
                        }
                    ) or None,
                    "external_dataset_root": sorted(
                        {
                            str(source.get("dataset_root"))
                            for source in automatic_external_sources_by_run_id.values()
                            if source.get("dataset_root") is not None
                        }
                    ) or None,
                    "audit_dir": None,
                    "audit_dataset_catalog_id": None,
                    "audit_dataset_root": None,
                    "matched_champion_count": len(champions),
                    "rows_generated": len(external_rows),
                    "skipped_champions": external_skipped,
                    "external_scope_summary": build_scope_summary(automatic_external_sources_by_run_id),
                    "resolution_warnings": build_resolution_warnings(
                        "external",
                        automatic_external_sources_by_run_id,
                    ),
                },
                external_evaluations_run=external_count,
                audit_evaluations_run=0,
                report_name="external_reevaluation_report.txt",
                json_name="external_reevaluated_champions.json",
                include_csv=False,
            )
        except ValueError as exc:
            print(f"WARNING: external multiseed validation skipped -> {exc}")
            external_result = write_skip_reevaluation(
                external_output_dir,
                "Post-multiseed external validation",
                str(exc),
                status="failed",
                report_name="external_reevaluation_report.txt",
                json_name="external_reevaluated_champions.json",
            )
    else:
        print(
            "WARNING: external multiseed validation skipped -> "
            f"directory not found: {external_validation_dir}"
        )
        external_result = write_skip_reevaluation(
            external_output_dir,
            "Post-multiseed external validation",
            (
                f"Dataset directory not found: {external_validation_dir}"
                if external_validation_dir is not None
                else "No automatic catalog-scoped external datasets were found for this multiseed execution."
            ),
            status="skipped_missing_dir" if external_validation_dir is not None else "not_run",
            report_name="external_reevaluation_report.txt",
            json_name="external_reevaluated_champions.json",
        )

    audit_requested = (
        audit_dir is not None
        or any(source.get("dataset_paths") for source in automatic_audit_sources_by_run_id.values())
    )
    if audit_dir is not None and audit_dir.exists():
        try:
            audit_rows, _, audit_count, audit_skipped = build_reevaluation_rows(
                champions=champions,
                audit_dir=audit_dir,
            )
            audit_result = write_reevaluation_outputs(
                rows=audit_rows,
                output_path=audit_output_dir,
                filters={
                    "db_path": "automatic_post_multiseed",
                    "dataset_root": None,
                    "config_name": "multiple",
                    "run_id": "multiple",
                    "run_ids": sorted({summary.run_id for summary in run_summaries}),
                    "reevaluation_run_ids": sorted({champion["run_id"] for champion in champions}),
                    "champion_type": None,
                    "limit": None,
                    "external_validation_dir": None,
                    "external_dataset_catalog_id": None,
                    "external_dataset_root": None,
                    "audit_dir": audit_dir,
                    "audit_dataset_catalog_id": None,
                    "audit_dataset_root": audit_dir,
                    "matched_champion_count": len(champions),
                    "rows_generated": len(audit_rows),
                    "skipped_champions": audit_skipped,
                    "audit_scope_summary": build_scope_summary(automatic_audit_sources_by_run_id),
                    "resolution_warnings": build_resolution_warnings(
                        "audit",
                        automatic_audit_sources_by_run_id,
                    ),
                },
                external_evaluations_run=0,
                audit_evaluations_run=audit_count,
                report_name="audit_reevaluation_report.txt",
                json_name="audit_reevaluated_champions.json",
                include_csv=False,
            )
        except ValueError as exc:
            print(f"WARNING: audit multiseed validation skipped -> {exc}")
            audit_result = write_skip_reevaluation(
                audit_output_dir,
                "Post-multiseed audit validation",
                str(exc),
                status="failed",
                report_name="audit_reevaluation_report.txt",
                json_name="audit_reevaluated_champions.json",
            )
    elif audit_dir is None and audit_requested:
        try:
            audit_rows, _, audit_count, audit_skipped = build_reevaluation_rows(
                champions=champions,
                audit_sources_by_run_id=automatic_audit_sources_by_run_id,
            )
            audit_result = write_reevaluation_outputs(
                rows=audit_rows,
                output_path=audit_output_dir,
                filters={
                    "db_path": "automatic_post_multiseed",
                    "dataset_root": None,
                    "config_name": "multiple",
                    "run_id": "multiple",
                    "run_ids": sorted({summary.run_id for summary in run_summaries}),
                    "reevaluation_run_ids": sorted({champion["run_id"] for champion in champions}),
                    "champion_type": None,
                    "limit": None,
                    "external_validation_dir": None,
                    "external_dataset_catalog_id": None,
                    "external_dataset_root": None,
                    "audit_dir": None,
                    "audit_dataset_catalog_id": sorted(
                        {
                            source.get("dataset_catalog_id")
                            for source in automatic_audit_sources_by_run_id.values()
                            if source.get("dataset_catalog_id")
                        }
                    ) or None,
                    "audit_dataset_root": sorted(
                        {
                            str(source.get("dataset_root"))
                            for source in automatic_audit_sources_by_run_id.values()
                            if source.get("dataset_root") is not None
                        }
                    ) or None,
                    "matched_champion_count": len(champions),
                    "rows_generated": len(audit_rows),
                    "skipped_champions": audit_skipped,
                    "audit_scope_summary": build_scope_summary(automatic_audit_sources_by_run_id),
                    "resolution_warnings": build_resolution_warnings(
                        "audit",
                        automatic_audit_sources_by_run_id,
                    ),
                },
                external_evaluations_run=0,
                audit_evaluations_run=audit_count,
                report_name="audit_reevaluation_report.txt",
                json_name="audit_reevaluated_champions.json",
                include_csv=False,
            )
        except ValueError as exc:
            print(f"WARNING: audit multiseed validation skipped -> {exc}")
            audit_result = write_skip_reevaluation(
                audit_output_dir,
                "Post-multiseed audit validation",
                str(exc),
                status="failed",
                report_name="audit_reevaluation_report.txt",
                json_name="audit_reevaluated_champions.json",
            )
    else:
        print(
            "WARNING: audit multiseed validation skipped -> "
            f"directory not found: {audit_dir}"
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            "Post-multiseed audit validation",
            (
                f"Dataset directory not found: {audit_dir}"
                if audit_dir is not None
                else "No automatic catalog-scoped audit datasets were found for this multiseed execution."
            ),
            status="skipped_missing_dir" if audit_dir is not None else "not_run",
            report_name="audit_reevaluation_report.txt",
            json_name="audit_reevaluated_champions.json",
        )

    return external_result, audit_result


def run_post_multiseed_analysis(
    *,
    multiseed_dir: Path,
    summary_path: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    persistence_db_path: Path = DEFAULT_PERSISTENCE_DB_PATH,
    multiseed_run_id: int | None = None,
    external_validation_dir: Path | None = None,
    audit_dir: Path | None = None,
    failures: list[str] | None = None,
    seeds_planned: int,
    seeds_executed: int,
    seeds_reused: int,
) -> PostMultiseedAnalysisResult:
    failures = failures or []
    analysis_dir = multiseed_dir / ANALYSIS_DIRNAME
    debug_dir = multiseed_dir / DEBUG_DIRNAME
    analysis_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)

    run_ids = [summary.run_id for summary in run_summaries]
    run_execution_contexts = load_run_execution_contexts(
        persistence_db_path,
        run_ids,
    )
    automatic_external_sources_by_run_id, automatic_audit_sources_by_run_id = (
        resolve_automatic_validation_sources_by_run_id(run_execution_contexts)
    )
    external_scope_summary = build_scope_summary(automatic_external_sources_by_run_id)
    audit_scope_summary = build_scope_summary(automatic_audit_sources_by_run_id)
    persisted_champions = load_persisted_multiseed_champions(
        persistence_db_path,
        run_ids,
    )
    champions_analysis_dir = debug_dir / CHAMPIONS_ANALYSIS_DIRNAME
    champion_analysis_result = None
    if persisted_champions:
        champion_analysis_result = analyze_champions(
            db_path=persistence_db_path,
            output_dir=champions_analysis_dir,
            run_ids=run_ids,
            persist_analysis=False,
        )

    post_multiseed_validation_dir = debug_dir / POST_MULTISEED_VALIDATION_DIRNAME
    external_output_dir = post_multiseed_validation_dir / "external"
    audit_output_dir = post_multiseed_validation_dir / "audit"
    external_result, audit_result = run_post_execution_validation(
        champions=persisted_champions,
        run_summaries=run_summaries,
        external_validation_dir=external_validation_dir,
        audit_dir=audit_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
        automatic_external_sources_by_run_id=automatic_external_sources_by_run_id,
        automatic_audit_sources_by_run_id=automatic_audit_sources_by_run_id,
    )
    write_post_multiseed_reevaluation_summary(
        post_multiseed_validation_dir,
        external_result=external_result,
        audit_result=audit_result,
        external_scope_summary=external_scope_summary,
        audit_scope_summary=audit_scope_summary,
    )
    champion_analysis_status = (
        persist_automatic_champion_analysis(
            persistence_db_path=persistence_db_path,
            multiseed_run_id=multiseed_run_id,
            run_summaries=run_summaries,
            champion_rows=persisted_champions,
            champion_analysis_result=champion_analysis_result,
        )
        if multiseed_run_id is not None
        else ("completed" if champion_analysis_result is not None else "skipped_no_champions")
    )
    external_evaluation_status = (
        persist_automatic_champion_evaluation(
            persistence_db_path=persistence_db_path,
            multiseed_run_id=multiseed_run_id,
            run_summaries=run_summaries,
            champion_rows=persisted_champions,
            evaluation_type="external",
            result=external_result,
        )
        if multiseed_run_id is not None
        else external_result.get("status", "failed")
    )
    audit_evaluation_status = (
        persist_automatic_champion_evaluation(
            persistence_db_path=persistence_db_path,
            multiseed_run_id=multiseed_run_id,
            run_summaries=run_summaries,
            champion_rows=persisted_champions,
            evaluation_type="audit",
            result=audit_result,
        )
        if multiseed_run_id is not None
        else audit_result.get("status", "failed")
    )

    decision_payload = build_multiseed_decision_payload(
        run_summaries=run_summaries,
        champion_count=len(persisted_champions),
        champion_analysis_result=champion_analysis_result,
        external_result=external_result,
        audit_result=audit_result,
        failures=failures,
        seeds_planned=seeds_planned,
        seeds_executed=seeds_executed,
        seeds_reused=seeds_reused,
    )
    quick_summary_path = write_multiseed_quick_summary(
        multiseed_dir=multiseed_dir,
        dataset_root_label=dataset_root_label,
        decision_payload=decision_payload,
    )

    champions_summary_path = write_multiseed_champions_summary(
        analysis_dir=analysis_dir,
        decision_payload=decision_payload,
        champion_analysis_result=champion_analysis_result,
        external_result=external_result,
        audit_result=audit_result,
    )

    return PostMultiseedAnalysisResult(
        summary_path=summary_path,
        quick_summary_path=quick_summary_path,
        champions_summary_path=champions_summary_path,
        analysis_dir=analysis_dir,
        debug_dir=debug_dir,
        champions_analysis_dir=champions_analysis_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
        champion_count=len(persisted_champions),
        champion_analysis_status=champion_analysis_status,
        external_evaluation_status=external_evaluation_status,
        audit_evaluation_status=audit_evaluation_status,
        verdict=decision_payload["verdict"],
        recommended_next_action=decision_payload["recommended_next_action"],
    )
