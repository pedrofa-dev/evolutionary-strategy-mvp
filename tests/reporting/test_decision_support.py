from pathlib import Path

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.reporting.decision_support import (
    NO_EDGE_DETECTED,
    OVERFIT_SUSPECT,
    ROBUST_CANDIDATE,
    build_multiseed_decision_payload,
)


def build_summary(run_id: str, selection: float, profit: float) -> HistoricalRunSummary:
    return HistoricalRunSummary(
        config_name="config_a.json",
        run_id=run_id,
        log_file_path=Path("run.txt"),
        mutation_seed=42,
        best_train_selection_score=selection + 0.1,
        final_validation_selection_score=selection,
        final_validation_profit=profit,
        final_validation_drawdown=0.01,
        final_validation_trades=12.0,
        best_genome_repr="genome",
        generation_of_best=5,
        train_validation_selection_gap=0.1,
        train_validation_profit_gap=0.01,
    )


def test_build_multiseed_decision_payload_detects_no_edge() -> None:
    payload = build_multiseed_decision_payload(
        run_summaries=[build_summary("run-001", 0.8, -0.01)],
        champion_count=0,
        champion_analysis_result=None,
        external_result={"rows": []},
        audit_result={"rows": []},
        failures=[],
        seeds_planned=6,
        seeds_executed=6,
        seeds_reused=0,
    )

    assert payload["verdict"] == NO_EDGE_DETECTED
    assert "Add or change signals/features" in payload["recommended_next_action"]


def test_build_multiseed_decision_payload_detects_overfit() -> None:
    payload = build_multiseed_decision_payload(
        run_summaries=[
            build_summary("run-001", 1.6, 0.03),
            build_summary("run-002", 1.5, 0.025),
            build_summary("run-003", 1.4, 0.02),
            build_summary("run-004", 1.45, 0.022),
        ],
        champion_count=2,
        champion_analysis_result={
            "report_data": {
                "patterns": {},
                "top_examples": {
                    "best_validation_selection": {
                        "run_id": "run-001",
                        "config_name": "config_a.json",
                        "validation_selection": 1.6,
                        "validation_profit": 0.03,
                    }
                },
            }
        },
        external_result={
            "rows": [
                {
                    "external_validation_selection": -0.2,
                    "external_validation_profit": -0.01,
                    "external_validation_drawdown": 0.03,
                    "external_validation_trades": 8,
                    "external_validation_is_valid": False,
                    "external_validation_negative_datasets": 1,
                }
            ]
        },
        audit_result={"rows": []},
        failures=[],
        seeds_planned=6,
        seeds_executed=6,
        seeds_reused=0,
    )

    assert payload["verdict"] == OVERFIT_SUSPECT
    assert payload["external_summary"]["pass_label"] == "FAIL"


def test_build_multiseed_decision_payload_detects_robust_candidate() -> None:
    payload = build_multiseed_decision_payload(
        run_summaries=[
            HistoricalRunSummary(
                config_name="config_a.json",
                run_id="run-001",
                log_file_path=Path("run.txt"),
                mutation_seed=42,
                best_train_selection_score=1.8,
                final_validation_selection_score=1.7,
                final_validation_profit=0.03,
                final_validation_drawdown=0.01,
                final_validation_trades=14.0,
                best_genome_repr="genome",
                generation_of_best=5,
                train_validation_selection_gap=0.2,
                train_validation_profit_gap=0.01,
            ),
            HistoricalRunSummary(
                config_name="config_b.json",
                run_id="run-002",
                log_file_path=Path("run.txt"),
                mutation_seed=43,
                best_train_selection_score=1.75,
                final_validation_selection_score=1.65,
                final_validation_profit=0.028,
                final_validation_drawdown=0.012,
                final_validation_trades=15.0,
                best_genome_repr="genome",
                generation_of_best=6,
                train_validation_selection_gap=0.15,
                train_validation_profit_gap=0.01,
            ),
            HistoricalRunSummary(
                config_name="config_a.json",
                run_id="run-003",
                log_file_path=Path("run.txt"),
                mutation_seed=44,
                best_train_selection_score=1.7,
                final_validation_selection_score=1.6,
                final_validation_profit=0.027,
                final_validation_drawdown=0.011,
                final_validation_trades=13.0,
                best_genome_repr="genome",
                generation_of_best=4,
                train_validation_selection_gap=0.1,
                train_validation_profit_gap=0.01,
            ),
            HistoricalRunSummary(
                config_name="config_b.json",
                run_id="run-004",
                log_file_path=Path("run.txt"),
                mutation_seed=45,
                best_train_selection_score=1.78,
                final_validation_selection_score=1.68,
                final_validation_profit=0.029,
                final_validation_drawdown=0.01,
                final_validation_trades=14.0,
                best_genome_repr="genome",
                generation_of_best=7,
                train_validation_selection_gap=0.12,
                train_validation_profit_gap=0.01,
            ),
        ],
        champion_count=3,
        champion_analysis_result={
            "report_data": {
                "patterns": {
                    "weight_sign_bias": {
                        "weight_trend_long": {"type": "mostly_positive", "positive_rate": 0.8}
                    }
                },
                "top_examples": {
                    "best_validation_selection": {
                        "run_id": "run-001",
                        "config_name": "config_a.json",
                        "validation_selection": 1.7,
                        "validation_profit": 0.03,
                        "selection_gap": 0.2,
                        "validation_dispersion": 0.1,
                    }
                },
            }
        },
        external_result={
            "rows": [
                {
                    "external_validation_selection": 1.4,
                    "external_validation_profit": 0.02,
                    "external_validation_drawdown": 0.012,
                    "external_validation_trades": 12,
                    "external_validation_is_valid": True,
                    "external_validation_negative_datasets": 0,
                }
            ]
        },
        audit_result={"rows": []},
        failures=[],
        seeds_planned=6,
        seeds_executed=4,
        seeds_reused=2,
    )

    assert payload["verdict"] == ROBUST_CANDIDATE
    assert payload["external_summary"]["pass_label"] == "PASS"
