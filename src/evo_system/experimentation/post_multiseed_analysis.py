from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Callable
import uuid

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.dataset_roots import DEFAULT_DATASET_ROOT
from evo_system.experimentation.historical_run import DEFAULT_EXTERNAL_VALIDATION_DIR
from evo_system.experimentation.persisted_champion_reevaluation import (
    build_reevaluation_rows,
    filter_champions,
    write_reevaluation_outputs,
)
from evo_system.reporting.report_builder import analyze_champions
from evo_system.storage import (
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
)
from evo_system.storage.persistence_store import serialize_json, sha256_hex
from evo_system.storage.sqlite_store import SQLiteStore


DEFAULT_AUDIT_DIR = DEFAULT_DATASET_ROOT / "audit"
MULTISEED_QUICK_SUMMARY_NAME = "multiseed_quick_summary.txt"
MULTISEED_CHAMPIONS_SUMMARY_NAME = "multiseed_champions_summary.txt"
CHAMPIONS_ANALYSIS_DIRNAME = "champions_analysis"
POST_MULTISEED_VALIDATION_DIRNAME = "post_multiseed_validation"


@dataclass(frozen=True)
class PostMultiseedAnalysisResult:
    summary_path: Path
    quick_summary_path: Path
    champions_summary_path: Path
    champions_analysis_dir: Path
    external_output_dir: Path
    audit_output_dir: Path
    champion_count: int
    champion_analysis_status: str
    external_evaluation_status: str
    audit_evaluation_status: str


def build_config_paths_by_run_id(
    run_summaries: list[HistoricalRunSummary],
) -> dict[str, Path]:
    return {
        summary.run_id: summary.config_path
        for summary in run_summaries
        if summary.config_path is not None
    }


def build_multiseed_quick_summary_lines(
    multiseed_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    failures: list[str],
    seeds_planned: int,
) -> list[str]:
    config_names = sorted({summary.config_name for summary in run_summaries})
    if not config_names:
        config_label = "none"
    elif len(config_names) == 1:
        config_label = config_names[0]
    else:
        config_label = f"{len(config_names)} configs"

    lines = [
        f"Multiseed directory: {multiseed_dir}",
        f"Multiseed identifier: {multiseed_dir.name}",
        f"Config executed: {config_label}",
        f"Dataset root: {dataset_root_label}",
        f"Seeds planned: {seeds_planned}",
        f"Seeds completed: {len(run_summaries)}",
        f"Seeds failed: {len(failures)}",
    ]

    top_candidate = next(
        (
            summary
            for summary in sorted(
                run_summaries,
                key=lambda item: item.final_validation_selection_score,
                reverse=True,
            )
            if summary.final_validation_profit > 0.0
        ),
        None,
    )
    lines.append(
        "Champion candidate: "
        + (
            f"run_id={top_candidate.run_id} | seed={top_candidate.mutation_seed} | "
            f"validation_selection={top_candidate.final_validation_selection_score:.4f}"
            if top_candidate is not None
            else "none"
        )
    )

    lines.extend(
        build_quick_top_lines(
            run_summaries,
            first_field_label="seed",
            first_field_value=lambda summary: str(summary.mutation_seed),
        )
    )

    lines.append("")
    lines.append("Failures")
    if failures:
        for failure in failures[:5]:
            lines.append(f"  {failure}")
    else:
        lines.append("  No failures.")

    return lines


def write_multiseed_quick_summary(
    multiseed_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    failures: list[str],
    seeds_planned: int,
) -> Path:
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    quick_summary_path = multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    quick_summary_path.write_text(
        "\n".join(
            build_multiseed_quick_summary_lines(
                multiseed_dir=multiseed_dir,
                run_summaries=run_summaries,
                dataset_root_label=dataset_root_label,
                failures=failures,
                seeds_planned=seeds_planned,
            )
        ),
        encoding="utf-8",
    )
    return quick_summary_path


def load_multiseed_champions(db_path: Path, run_ids: list[str]) -> list[dict[str, Any]]:
    store = SQLiteStore(str(db_path))
    store.initialize()
    return filter_champions(store.load_champions(), run_ids=run_ids)


def load_persisted_multiseed_champions(
    persistence_db_path: Path,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    return store.load_champions(run_ids=run_ids)


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
    evaluation_member_ids = select_matching_champion_ids(champion_rows, rows)
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    evaluation_id = store.save_champion_evaluation(
        champion_evaluation_uid=str(uuid.uuid4()),
        multiseed_run_id=multiseed_run_id,
        evaluation_type=evaluation_type,
        evaluation_origin="automatic_post_multiseed",
        champion_count=len(champion_rows),
        dataset_source_type=rows[0].get(f"{dataset_prefix}_source_type") or "unknown",
        dataset_set_name=rows[0].get(f"{dataset_prefix}_dataset_set_name") or evaluation_type,
        dataset_catalog_id=rows[0].get(f"{dataset_prefix}_dataset_catalog_id"),
        dataset_root=rows[0].get(f"{dataset_prefix}_dataset_root"),
        dataset_signature=build_dataset_set_signature(rows=rows, dataset_prefix=dataset_prefix),
        selection_scope_json=build_champion_selection_scope(run_summaries, champion_rows),
        evaluation_summary_json={
            "rows_generated": result.get("rows_generated", len(rows)),
            "external_evaluations_run": result.get("external_evaluations_run", 0),
            "audit_evaluations_run": result.get("audit_evaluations_run", 0),
            "mean_summary": summarize_rows(rows, metrics_prefix),
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


def build_quick_top_lines(
    run_summaries: list[HistoricalRunSummary],
    *,
    first_field_label: str,
    first_field_value: Callable[[HistoricalRunSummary], str],
) -> list[str]:
    lines = [
        "",
        "Top 3 by validation selection",
    ]

    for index, summary in enumerate(
        sorted(
            run_summaries,
            key=lambda item: item.final_validation_selection_score,
            reverse=True,
        )[:3],
        start=1,
    ):
        lines.append(
            f"  {index}. run_id={summary.run_id} | "
            f"{first_field_label}={first_field_value(summary)} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_profit={summary.final_validation_profit:.4f}"
        )

    lines.append("")
    lines.append("Top 3 by validation profit")
    for index, summary in enumerate(
        sorted(
            run_summaries,
            key=lambda item: item.final_validation_profit,
            reverse=True,
        )[:3],
        start=1,
    ):
        lines.append(
            f"  {index}. run_id={summary.run_id} | "
            f"{first_field_label}={first_field_value(summary)} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f}"
        )

    return lines


def write_skip_reevaluation(
    output_dir: Path,
    title: str,
    reason: str,
    *,
    status: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "reevaluation_report.txt"
    csv_path = output_dir / "reevaluated_champions.csv"
    json_path = output_dir / "reevaluated_champions.json"
    champions_dir = output_dir / "champions"
    champions_dir.mkdir(parents=True, exist_ok=True)

    report_path.write_text(f"{title}\n\n{reason}\n", encoding="utf-8")
    csv_path.write_text("", encoding="utf-8")
    json_path.write_text("[]", encoding="utf-8")

    return {
        "rows": [],
        "output_dir": output_dir,
        "csv_path": csv_path,
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


def run_post_execution_validation(
    *,
    champions: list[dict[str, Any]],
    run_summaries: list[HistoricalRunSummary],
    db_path: Path,
    external_validation_dir: Path,
    audit_dir: Path,
    external_output_dir: Path,
    audit_output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not champions:
        external_result = write_skip_reevaluation(
            external_output_dir,
            "Post-multiseed external validation",
            "No persisted champions were found for this multiseed execution.",
            status="skipped_no_champions",
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            "Post-multiseed audit validation",
            "No persisted champions were found for this multiseed execution.",
            status="skipped_no_champions",
        )
        return external_result, audit_result

    config_paths_by_run_id = build_config_paths_by_run_id(run_summaries)

    if external_validation_dir.exists():
        try:
            external_rows, external_count, _, external_skipped = build_reevaluation_rows(
                champions=champions,
                config_paths_by_run_id=config_paths_by_run_id,
                external_validation_dir=external_validation_dir,
            )
            external_result = write_reevaluation_outputs(
                rows=external_rows,
                output_path=external_output_dir,
                filters={
                    "db_path": db_path,
                    "config_path": "multiple",
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
                },
                external_evaluations_run=external_count,
                audit_evaluations_run=0,
            )
        except ValueError as exc:
            print(f"WARNING: external multiseed validation skipped -> {exc}")
            external_result = write_skip_reevaluation(
                external_output_dir,
                "Post-multiseed external validation",
                str(exc),
                status="failed",
            )
    else:
        print(
            "WARNING: external multiseed validation skipped -> "
            f"directory not found: {external_validation_dir}"
        )
        external_result = write_skip_reevaluation(
            external_output_dir,
            "Post-multiseed external validation",
            f"Dataset directory not found: {external_validation_dir}",
            status="skipped_missing_dir",
        )

    if audit_dir.exists():
        try:
            audit_rows, _, audit_count, audit_skipped = build_reevaluation_rows(
                champions=champions,
                config_paths_by_run_id=config_paths_by_run_id,
                audit_dir=audit_dir,
            )
            audit_result = write_reevaluation_outputs(
                rows=audit_rows,
                output_path=audit_output_dir,
                filters={
                    "db_path": db_path,
                    "config_path": "multiple",
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
                },
                external_evaluations_run=0,
                audit_evaluations_run=audit_count,
            )
        except ValueError as exc:
            print(f"WARNING: audit multiseed validation skipped -> {exc}")
            audit_result = write_skip_reevaluation(
                audit_output_dir,
                "Post-multiseed audit validation",
                str(exc),
                status="failed",
            )
    else:
        print(
            "WARNING: audit multiseed validation skipped -> "
            f"directory not found: {audit_dir}"
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            "Post-multiseed audit validation",
            f"Dataset directory not found: {audit_dir}",
            status="skipped_missing_dir",
        )

    return external_result, audit_result


def write_multiseed_champions_summary(
    multiseed_dir: Path,
    champion_count: int,
    champion_analysis_result: dict[str, Any] | None,
    external_result: dict[str, Any],
    audit_result: dict[str, Any],
) -> Path:
    summary_path = multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
    lines = [
        "Multiseed champions summary",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Champions found in multiseed: {champion_count}",
        "",
    ]

    if champion_count == 0:
        lines.append("No persisted champions were produced by this multiseed execution.")
        summary_path.write_text("\n".join(lines), encoding="utf-8")
        return summary_path

    lines.append("Champions observed across seeds")
    if champion_analysis_result is None:
        lines.append("  Champion analysis could not be generated.")
    else:
        report_data = champion_analysis_result["report_data"]
        top_examples = report_data.get("top_examples", {})
        if top_examples:
            for label, row in top_examples.items():
                lines.append(
                    f"  {label}: id={row.get('id')} | "
                    f"config={row.get('config_name')} | "
                    f"run_id={row.get('run_id')} | "
                    f"validation_selection={float(row.get('validation_selection', 0.0)):.4f} | "
                    f"validation_profit={float(row.get('validation_profit', 0.0)):.4f}"
                )
        else:
            lines.append("  No top examples available.")

    lines.append("")
    lines.append("Best multiseed candidates")
    lines.extend(build_candidate_lines(external_result["rows"], "external_validation_selection"))

    lines.append("")
    lines.append("External behavior")
    external_summary = summarize_rows(external_result["rows"], "external_validation")
    if external_result["rows"]:
        lines.append(
            f"  mean_validation_selection={external_summary['mean_validation_selection']}"
        )
        lines.append(f"  mean_external_selection={external_summary['mean_post_selection']}")
        lines.append(
            f"  mean_validation_profit={external_summary['mean_validation_profit']}"
        )
        lines.append(f"  mean_external_profit={external_summary['mean_post_profit']}")
        lines.append(
            f"  champions_with_positive_external_profit={external_summary['positive_profit_count']}"
        )
        lines.append(
            f"  champions_with_valid_external={external_summary['valid_count']}"
        )
    else:
        lines.append("  External datasets not evaluated or no champions available.")

    lines.append("")
    lines.append("Audit behavior")
    audit_summary = summarize_rows(audit_result["rows"], "audit")
    if audit_result["rows"]:
        lines.append(
            f"  mean_validation_selection={audit_summary['mean_validation_selection']}"
        )
        lines.append(f"  mean_audit_selection={audit_summary['mean_post_selection']}")
        lines.append(
            f"  mean_validation_profit={audit_summary['mean_validation_profit']}"
        )
        lines.append(f"  mean_audit_profit={audit_summary['mean_post_profit']}")
        lines.append(
            f"  champions_with_positive_audit_profit={audit_summary['positive_profit_count']}"
        )
        lines.append(f"  champions_with_valid_audit={audit_summary['valid_count']}")
    else:
        lines.append("  Audit datasets not evaluated or no champions available.")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def run_post_multiseed_analysis(
    *,
    multiseed_dir: Path,
    summary_path: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    db_path: Path,
    persistence_db_path: Path = DEFAULT_PERSISTENCE_DB_PATH,
    multiseed_run_id: int | None = None,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    failures: list[str] | None = None,
    seeds_planned: int,
) -> PostMultiseedAnalysisResult:
    failures = failures or []

    quick_summary_path = write_multiseed_quick_summary(
        multiseed_dir=multiseed_dir,
        run_summaries=run_summaries,
        dataset_root_label=dataset_root_label,
        failures=failures,
        seeds_planned=seeds_planned,
    )

    run_ids = [summary.run_id for summary in run_summaries]
    champions = load_multiseed_champions(db_path, run_ids)
    persisted_champions = load_persisted_multiseed_champions(
        persistence_db_path,
        run_ids,
    )
    champions_analysis_dir = multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME
    champion_analysis_result = None
    if champions:
        champion_analysis_result = analyze_champions(
            db_path=persistence_db_path,
            output_dir=champions_analysis_dir,
            run_ids=run_ids,
            persist_analysis=False,
        )

    post_multiseed_validation_dir = multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME
    external_output_dir = post_multiseed_validation_dir / "external"
    audit_output_dir = post_multiseed_validation_dir / "audit"
    external_result, audit_result = run_post_execution_validation(
        champions=champions,
        run_summaries=run_summaries,
        db_path=db_path,
        external_validation_dir=external_validation_dir,
        audit_dir=audit_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
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

    champions_summary_path = write_multiseed_champions_summary(
        multiseed_dir=multiseed_dir,
        champion_count=len(champions),
        champion_analysis_result=champion_analysis_result,
        external_result=external_result,
        audit_result=audit_result,
    )

    return PostMultiseedAnalysisResult(
        summary_path=summary_path,
        quick_summary_path=quick_summary_path,
        champions_summary_path=champions_summary_path,
        champions_analysis_dir=champions_analysis_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
        champion_count=len(persisted_champions),
        champion_analysis_status=champion_analysis_status,
        external_evaluation_status=external_evaluation_status,
        audit_evaluation_status=audit_evaluation_status,
    )
