from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimental_space.identity import (
    format_experimental_space_summary_label,
    summarize_experimental_space_snapshots,
)


NO_EDGE_DETECTED = "NO_EDGE_DETECTED"
OVERFIT_SUSPECT = "OVERFIT_SUSPECT"
WEAK_PROMISING = "WEAK_PROMISING"
ROBUST_CANDIDATE = "ROBUST_CANDIDATE"
DATASET_LIMIT = "DATASET_LIMIT"
GENOME_POLICY_LIMIT = "GENOME_POLICY_LIMIT"
INSUFFICIENT_DIVERSITY = "INSUFFICIENT_DIVERSITY"

SIGNAL_SPACE_LIMIT = "SIGNAL_SPACE_LIMIT"
GENERALIZATION_LIMIT = "GENERALIZATION_LIMIT"
DATASET_COVERAGE_LIMIT = "DATASET_COVERAGE_LIMIT"
GENOME_POLICY_BOTTLENECK = "GENOME_POLICY_LIMIT"
NO_CLEAR_LIMIT = "NO_CLEAR_LIMIT"


def safe_mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def safe_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return pstdev(values)


def summarize_validation_runs(
    run_summaries: list[HistoricalRunSummary],
) -> dict[str, Any]:
    selections = [summary.final_validation_selection_score for summary in run_summaries]
    profits = [summary.final_validation_profit for summary in run_summaries]
    drawdowns = [summary.final_validation_drawdown for summary in run_summaries]
    trades = [summary.final_validation_trades for summary in run_summaries]
    selection_gaps = [abs(summary.train_validation_selection_gap) for summary in run_summaries]
    profit_gaps = [abs(summary.train_validation_profit_gap) for summary in run_summaries]

    return {
        "run_count": len(run_summaries),
        "mean_validation_selection": safe_mean(selections),
        "mean_validation_profit": safe_mean(profits),
        "mean_validation_drawdown": safe_mean(drawdowns),
        "mean_validation_trades": safe_mean(trades),
        "mean_abs_selection_gap": safe_mean(selection_gaps),
        "mean_abs_profit_gap": safe_mean(profit_gaps),
        "validation_selection_dispersion": safe_std(selections),
    }


def summarize_post_stage(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    selections = [
        float(row[f"{prefix}_selection"])
        for row in rows
        if row.get(f"{prefix}_selection") is not None
    ]
    profits = [
        float(row[f"{prefix}_profit"])
        for row in rows
        if row.get(f"{prefix}_profit") is not None
    ]
    drawdowns = [
        float(row[f"{prefix}_drawdown"])
        for row in rows
        if row.get(f"{prefix}_drawdown") is not None
    ]
    trades = [
        float(row[f"{prefix}_trades"])
        for row in rows
        if row.get(f"{prefix}_trades") is not None
    ]
    valid_count = sum(1 for row in rows if bool(row.get(f"{prefix}_is_valid")))
    positive_profit_count = sum(
        1
        for row in rows
        if row.get(f"{prefix}_profit") is not None and float(row[f"{prefix}_profit"]) > 0.0
    )
    negative_dataset_count = sum(
        int(row.get(f"{prefix}_negative_datasets") or 0)
        for row in rows
    )

    if not rows:
        pass_label = "NOT_RUN"
    elif positive_profit_count > 0 and valid_count > 0:
        pass_label = "PASS"
    elif positive_profit_count > 0 or valid_count > 0:
        pass_label = "MIXED"
    else:
        pass_label = "FAIL"

    return {
        "rows": len(rows),
        "mean_selection": safe_mean(selections),
        "mean_profit": safe_mean(profits),
        "mean_drawdown": safe_mean(drawdowns),
        "mean_trades": safe_mean(trades),
        "valid_count": valid_count,
        "positive_profit_count": positive_profit_count,
        "negative_dataset_count": negative_dataset_count,
        "pass_label": pass_label,
    }


def build_pattern_highlights(report_data: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    patterns = report_data.get("patterns", {})

    weight_bias = patterns.get("weight_sign_bias", {})
    if weight_bias.get("weight_breakout", {}).get("type") == "mostly_positive":
        highlights.append("Breakout dependence appears repeatedly among persisted champions.")
    if weight_bias.get("weight_realized_volatility", {}).get("type") == "mostly_negative":
        highlights.append("Champions repeatedly avoid high realized-volatility contexts.")
    if weight_bias.get("weight_trend_long", {}).get("type") == "mostly_positive":
        highlights.append("Long-trend bias is recurrent across champions.")
    if weight_bias.get("weight_trend_strength", {}).get("type") == "mostly_positive":
        highlights.append("Trend-strength weighting appears consistently positive.")

    metric_summary = report_data.get("metric_summary", {})
    validation_trades = metric_summary.get("validation_trades", {})
    if validation_trades and validation_trades.get("mean", 0.0) < 10.0:
        highlights.append("Champions are low-trade; monetization may be limited by policy rigidity.")

    signal_patterns = patterns.get("signal_patterns", {})
    for field, data in signal_patterns.items():
        if data.get("type") == "recurrent_enabled":
            highlights.append(f"{field} is recurrently enabled across champions.")
        elif data.get("type") == "recurrent_disabled":
            highlights.append(f"{field} is recurrently disabled across champions.")

    return highlights[:5]


def classify_multiseed_verdict(
    *,
    champion_count: int,
    validation_summary: dict[str, Any],
    external_summary: dict[str, Any],
    audit_summary: dict[str, Any],
    config_count: int,
    pattern_highlights: list[str],
) -> dict[str, str]:
    if champion_count == 0:
        return {
            "verdict": NO_EDGE_DETECTED,
            "likely_limit": SIGNAL_SPACE_LIMIT,
            "explanation": "No champions survived validation, so the current signal set is not producing reliable edge.",
            "recommended_next_action": "Add or change signals/features before spending more time on reevaluation.",
        }

    if external_summary["pass_label"] == "NOT_RUN" and audit_summary["pass_label"] == "NOT_RUN":
        return {
            "verdict": WEAK_PROMISING,
            "likely_limit": GENERALIZATION_LIMIT,
            "explanation": "Validation produced champions, but external and audit batteries were not available, so generalization is still untested.",
            "recommended_next_action": "Build or point to catalog-scoped external and audit datasets before drawing a strong conclusion.",
        }

    if external_summary["pass_label"] == "FAIL" or audit_summary["pass_label"] == "FAIL":
        return {
            "verdict": OVERFIT_SUSPECT,
            "likely_limit": GENERALIZATION_LIMIT,
            "explanation": "Validation produced champions, but external or audit evaluation collapses materially.",
            "recommended_next_action": "Tighten entry filters and expand dataset coverage before adding more complexity.",
        }

    if validation_summary["run_count"] < 4 or config_count < 2:
        return {
            "verdict": DATASET_LIMIT,
            "likely_limit": DATASET_COVERAGE_LIMIT,
            "explanation": "The experiment set is too small or too narrow to support a strong robustness conclusion.",
            "recommended_next_action": "Expand seed and config coverage before making structural strategy changes.",
        }

    if champion_count >= 2 and config_count == 1:
        return {
            "verdict": INSUFFICIENT_DIVERSITY,
            "likely_limit": DATASET_COVERAGE_LIMIT,
            "explanation": "Champions are concentrated in one config family, so diversity is too low for a robust conclusion.",
            "recommended_next_action": "Broaden the active config set and dataset coverage before selecting a direction.",
        }

    mean_trades = validation_summary.get("mean_validation_trades") or 0.0
    mean_gap = validation_summary.get("mean_abs_selection_gap") or 0.0
    if mean_trades < 10.0 or mean_gap > 1.0:
        return {
            "verdict": GENOME_POLICY_LIMIT,
            "likely_limit": GENOME_POLICY_BOTTLENECK,
            "explanation": "Champions exist, but trade frequency or validation gap suggests the current decision policy is too rigid or unstable.",
            "recommended_next_action": "Change genome structure or entry/exit policy before widening the search.",
        }

    if external_summary["pass_label"] == "PASS" or audit_summary["pass_label"] == "PASS":
        return {
            "verdict": ROBUST_CANDIDATE,
            "likely_limit": NO_CLEAR_LIMIT,
            "explanation": "Validation remains positive and at least one post-run battery still supports the champions.",
            "recommended_next_action": "Promote the candidate set to a stricter friction and coverage follow-up experiment.",
        }

    if pattern_highlights:
        return {
            "verdict": WEAK_PROMISING,
            "likely_limit": GENERALIZATION_LIMIT,
            "explanation": "There are repeated champion patterns, but post-run evidence is still incomplete or mixed.",
            "recommended_next_action": "Keep the promising patterns, then run broader external and audit batteries before scaling up.",
        }

    return {
        "verdict": WEAK_PROMISING,
        "likely_limit": GENERALIZATION_LIMIT,
        "explanation": "Validation found champions, but the current evidence is not yet strong enough to claim robust generalization.",
        "recommended_next_action": "Run broader reevaluation batteries and tighten filters before the next large campaign.",
    }


def build_multiseed_decision_payload(
    *,
    run_summaries: list[HistoricalRunSummary],
    champion_count: int,
    champion_analysis_result: dict[str, Any] | None,
    external_result: dict[str, Any],
    audit_result: dict[str, Any],
    failures: list[str],
    seeds_planned: int,
    seeds_executed: int,
    seeds_reused: int,
) -> dict[str, Any]:
    validation_summary = summarize_validation_runs(run_summaries)
    external_summary = summarize_post_stage(external_result.get("rows", []), "external_validation")
    audit_summary = summarize_post_stage(audit_result.get("rows", []), "audit")
    report_data = champion_analysis_result.get("report_data", {}) if champion_analysis_result else {}
    pattern_highlights = build_pattern_highlights(report_data)
    top_examples = report_data.get("top_examples", {})
    best_candidate = top_examples.get("best_validation_selection")
    experimental_space_summary = summarize_experimental_space_snapshots(
        [getattr(summary, "experimental_space_snapshot", None) for summary in run_summaries]
    )

    verdict = classify_multiseed_verdict(
        champion_count=champion_count,
        validation_summary=validation_summary,
        external_summary=external_summary,
        audit_summary=audit_summary,
        config_count=len({summary.config_name for summary in run_summaries}),
        pattern_highlights=pattern_highlights,
    )

    return {
        "runs_planned": seeds_planned,
        "runs_completed": len(run_summaries),
        "runs_executed": seeds_executed,
        "runs_reused": seeds_reused,
        "runs_failed": len(failures),
        "champion_count": champion_count,
        "best_candidate": best_candidate,
        "validation_summary": validation_summary,
        "external_summary": external_summary,
        "audit_summary": audit_summary,
        "pattern_highlights": pattern_highlights,
        "experimental_space_summary": experimental_space_summary,
        "experimental_space_label": format_experimental_space_summary_label(
            experimental_space_summary
        ),
        "top_examples": top_examples,
        "verdict": verdict["verdict"],
        "likely_limit": verdict["likely_limit"],
        "explanation": verdict["explanation"],
        "recommended_next_action": verdict["recommended_next_action"],
        "failure_examples": failures[:3],
    }
