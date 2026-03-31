from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.persisted_champion_reevaluation import (
    build_reevaluation_rows,
    filter_champions,
    write_reevaluation_outputs,
)
from evo_system.experimentation.single_run import DEFAULT_EXTERNAL_VALIDATION_DIR
from evo_system.reporting.report_builder import analyze_champions
from evo_system.storage.sqlite_store import SQLiteStore


DEFAULT_AUDIT_DIR = Path("data/processed/audit")
BATCH_RUN_SUMMARY_NAME = "batch_run_summary.txt"
BATCH_QUICK_SUMMARY_NAME = "batch_quick_summary.txt"
BATCH_CHAMPIONS_SUMMARY_NAME = "batch_champions_summary.txt"
MULTISEED_QUICK_SUMMARY_NAME = "multiseed_quick_summary.txt"
MULTISEED_CHAMPIONS_SUMMARY_NAME = "multiseed_champions_summary.txt"
CHAMPIONS_ANALYSIS_DIRNAME = "champions_analysis"
POST_BATCH_VALIDATION_DIRNAME = "post_batch_validation"
POST_MULTISEED_VALIDATION_DIRNAME = "post_multiseed_validation"


@dataclass(frozen=True)
class PostBatchAnalysisResult:
    batch_summary_path: Path
    quick_summary_path: Path
    champions_summary_path: Path
    champions_analysis_dir: Path
    external_output_dir: Path
    audit_output_dir: Path


def build_config_paths_by_run_id(
    run_summaries: list[HistoricalRunSummary],
) -> dict[str, Path]:
    return {
        summary.run_id: summary.config_path
        for summary in run_summaries
        if summary.config_path is not None
    }


def build_batch_run_summary_lines(
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    batch_dir: Path,
) -> list[str]:
    lines = [
        f"Batch executed at: {datetime.now().isoformat(timespec='seconds')}",
        f"Batch directory: {batch_dir}",
        f"Dataset root: {dataset_root_label}",
        f"Runs executed: {len(run_summaries)}",
        "",
        "Ranking by final validation selection score",
    ]

    sorted_by_selection = sorted(
        run_summaries,
        key=lambda summary: summary.final_validation_selection_score,
        reverse=True,
    )
    for index, summary in enumerate(sorted_by_selection, start=1):
        lines.append(
            f"{index}. "
            f"{summary.config_name} | "
            f"run_id={summary.run_id} | "
            f"mutation_seed={summary.mutation_seed} | "
            f"best_train={summary.best_train_selection_score:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_drawdown={summary.final_validation_drawdown:.4f} | "
            f"validation_trades={summary.final_validation_trades:.1f} | "
            f"selection_gap={summary.train_validation_selection_gap:.4f} | "
            f"profit_gap={summary.train_validation_profit_gap:.4f}"
        )
        lines.append(f"  best_genome={summary.best_genome_repr}")
        lines.append(f"  log={summary.log_file_path}")
        lines.append("")

    lines.append("")
    lines.append("Ranking by final validation profit")

    sorted_by_profit = sorted(
        run_summaries,
        key=lambda summary: summary.final_validation_profit,
        reverse=True,
    )
    for index, summary in enumerate(sorted_by_profit, start=1):
        lines.append(
            f"{index}. "
            f"{summary.config_name} | "
            f"run_id={summary.run_id} | "
            f"mutation_seed={summary.mutation_seed} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_drawdown={summary.final_validation_drawdown:.4f} | "
            f"validation_trades={summary.final_validation_trades:.1f} | "
            f"selection_gap={summary.train_validation_selection_gap:.4f} | "
            f"profit_gap={summary.train_validation_profit_gap:.4f}"
        )
        lines.append(f"  best_genome={summary.best_genome_repr}")
        lines.append(f"  log={summary.log_file_path}")
        lines.append("")

    return lines


def write_batch_run_summary(
    batch_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
) -> Path:
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary_path = batch_dir / BATCH_RUN_SUMMARY_NAME
    summary_path.write_text(
        "\n".join(
            build_batch_run_summary_lines(
                run_summaries=run_summaries,
                dataset_root_label=dataset_root_label,
                batch_dir=batch_dir,
            )
        ),
        encoding="utf-8",
    )
    return summary_path


def build_batch_quick_summary_lines(
    batch_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    failures: list[str],
    runs_planned: int,
) -> list[str]:
    lines = [
        f"Batch directory: {batch_dir}",
        f"Batch identifier: {batch_dir.name}",
        f"Dataset root: {dataset_root_label}",
        f"Runs planned: {runs_planned}",
        f"Runs completed: {len(run_summaries)}",
        f"Runs failed: {len(failures)}",
    ]
    lines.extend(
        build_quick_top_lines(
            run_summaries,
            first_field_label="config_name",
            first_field_value=lambda summary: summary.config_name,
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


def write_batch_quick_summary(
    batch_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    failures: list[str],
    runs_planned: int,
) -> Path:
    batch_dir.mkdir(parents=True, exist_ok=True)
    quick_summary_path = batch_dir / BATCH_QUICK_SUMMARY_NAME
    quick_summary_path.write_text(
        "\n".join(
            build_batch_quick_summary_lines(
                batch_dir=batch_dir,
                run_summaries=run_summaries,
                dataset_root_label=dataset_root_label,
                failures=failures,
                runs_planned=runs_planned,
            )
        ),
        encoding="utf-8",
    )
    return quick_summary_path


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


def load_batch_champions(db_path: Path, run_ids: list[str]) -> list[dict[str, Any]]:
    store = SQLiteStore(str(db_path))
    store.initialize()
    return filter_champions(store.load_champions(), run_ids=run_ids)


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


def write_skip_reevaluation(output_dir: Path, title: str, reason: str) -> dict[str, Any]:
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


def write_batch_champions_summary(
    batch_dir: Path,
    champion_count: int,
    champion_analysis_result: dict[str, Any] | None,
    external_result: dict[str, Any],
    audit_result: dict[str, Any],
) -> Path:
    summary_path = batch_dir / BATCH_CHAMPIONS_SUMMARY_NAME
    lines = [
        "Batch champions summary",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Champions found in batch: {champion_count}",
        "",
    ]

    if champion_count == 0:
        lines.append("No persisted champions were produced by this batch.")
        summary_path.write_text("\n".join(lines), encoding="utf-8")
        return summary_path

    lines.append("Champions observed during the batch")
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
    lines.append("Best candidates leaving the batch")
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
        lines.append(
            f"  champions_with_valid_audit={audit_summary['valid_count']}"
        )
    else:
        lines.append("  Audit datasets not evaluated or no champions available.")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def run_post_execution_validation(
    *,
    champions: list[dict[str, Any]],
    run_summaries: list[HistoricalRunSummary],
    db_path: Path,
    external_validation_dir: Path,
    audit_dir: Path,
    external_output_dir: Path,
    audit_output_dir: Path,
    title_prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    execution_label = title_prefix.lower().removeprefix("post-")
    if not champions:
        external_result = write_skip_reevaluation(
            external_output_dir,
            f"{title_prefix} external validation",
            f"No persisted champions were found for this {execution_label}.",
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            f"{title_prefix} audit validation",
            f"No persisted champions were found for this {execution_label}.",
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
                    "external_dataset_mode": None,
                    "external_dataset_catalog_id": None,
                    "external_dataset_root": external_validation_dir,
                    "audit_dir": None,
                    "audit_dataset_mode": None,
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
            print(f"WARNING: external {execution_label} validation skipped -> {exc}")
            external_result = write_skip_reevaluation(
                external_output_dir,
                f"{title_prefix} external validation",
                str(exc),
            )
    else:
        print(
            f"WARNING: external {execution_label} validation skipped -> "
            f"directory not found: {external_validation_dir}"
        )
        external_result = write_skip_reevaluation(
            external_output_dir,
            f"{title_prefix} external validation",
            f"Dataset directory not found: {external_validation_dir}",
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
                    "external_dataset_mode": None,
                    "external_dataset_catalog_id": None,
                    "external_dataset_root": None,
                    "audit_dir": audit_dir,
                    "audit_dataset_mode": None,
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
            print(f"WARNING: audit {execution_label} validation skipped -> {exc}")
            audit_result = write_skip_reevaluation(
                audit_output_dir,
                f"{title_prefix} audit validation",
                str(exc),
            )
    else:
        print(
            f"WARNING: audit {execution_label} validation skipped -> "
            f"directory not found: {audit_dir}"
        )
        audit_result = write_skip_reevaluation(
            audit_output_dir,
            f"{title_prefix} audit validation",
            f"Dataset directory not found: {audit_dir}",
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


def run_post_batch_analysis(
    *,
    batch_dir: Path,
    run_summaries: list[HistoricalRunSummary],
    config_paths: list[Path],
    dataset_root_label: str,
    db_path: Path,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    failures: list[str] | None = None,
) -> PostBatchAnalysisResult:
    failures = failures or []

    batch_summary_path = write_batch_run_summary(
        batch_dir=batch_dir,
        run_summaries=run_summaries,
        dataset_root_label=dataset_root_label,
    )
    quick_summary_path = write_batch_quick_summary(
        batch_dir=batch_dir,
        run_summaries=run_summaries,
        dataset_root_label=dataset_root_label,
        failures=failures,
        runs_planned=len(config_paths),
    )

    run_ids = [summary.run_id for summary in run_summaries]
    champions = load_batch_champions(db_path, run_ids)
    champions_analysis_dir = batch_dir / CHAMPIONS_ANALYSIS_DIRNAME
    champion_analysis_result = None
    if champions:
        champion_analysis_result = analyze_champions(
            db_path=db_path,
            output_dir=champions_analysis_dir,
            run_ids=run_ids,
        )
    post_batch_validation_dir = batch_dir / POST_BATCH_VALIDATION_DIRNAME
    external_output_dir = post_batch_validation_dir / "external"
    audit_output_dir = post_batch_validation_dir / "audit"
    external_result, audit_result = run_post_execution_validation(
        champions=champions,
        run_summaries=run_summaries,
        db_path=db_path,
        external_validation_dir=external_validation_dir,
        audit_dir=audit_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
        title_prefix="Post-batch",
    )

    champions_summary_path = write_batch_champions_summary(
        batch_dir=batch_dir,
        champion_count=len(champions),
        champion_analysis_result=champion_analysis_result,
        external_result=external_result,
        audit_result=audit_result,
    )

    return PostBatchAnalysisResult(
        batch_summary_path=batch_summary_path,
        quick_summary_path=quick_summary_path,
        champions_summary_path=champions_summary_path,
        champions_analysis_dir=champions_analysis_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
    )


def run_post_multiseed_analysis(
    *,
    multiseed_dir: Path,
    summary_path: Path,
    run_summaries: list[HistoricalRunSummary],
    dataset_root_label: str,
    db_path: Path,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    failures: list[str] | None = None,
    seeds_planned: int,
) -> PostBatchAnalysisResult:
    failures = failures or []

    quick_summary_path = write_multiseed_quick_summary(
        multiseed_dir=multiseed_dir,
        run_summaries=run_summaries,
        dataset_root_label=dataset_root_label,
        failures=failures,
        seeds_planned=seeds_planned,
    )

    run_ids = [summary.run_id for summary in run_summaries]
    champions = load_batch_champions(db_path, run_ids)
    champions_analysis_dir = multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME
    champion_analysis_result = None
    if champions:
        champion_analysis_result = analyze_champions(
            db_path=db_path,
            output_dir=champions_analysis_dir,
            run_ids=run_ids,
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
        title_prefix="Post-multiseed",
    )

    champions_summary_path = write_multiseed_champions_summary(
        multiseed_dir=multiseed_dir,
        champion_count=len(champions),
        champion_analysis_result=champion_analysis_result,
        external_result=external_result,
        audit_result=audit_result,
    )

    return PostBatchAnalysisResult(
        batch_summary_path=summary_path,
        quick_summary_path=quick_summary_path,
        champions_summary_path=champions_summary_path,
        champions_analysis_dir=champions_analysis_dir,
        external_output_dir=external_output_dir,
        audit_output_dir=audit_output_dir,
    )
