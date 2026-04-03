import json
import sqlite3
from pathlib import Path

import pytest

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import Genome
from evo_system.experimentation.cli import build_parser
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    format_effective_dataset_roots,
    resolve_dataset_root,
)
from evo_system.experimentation.historical_run import execute_historical_run
from evo_system.experimentation.historical_run import build_initial_population
from evo_system.orchestration.config_loader import load_run_config
from evo_system.experimentation.multiseed_run import (
    CURRENT_LOGIC_VERSION,
    MULTISEED_RUN_SUMMARY_NAME,
    MultiseedExecutionOutcome,
    MultiseedJob,
    build_default_multiseed_seeds,
    build_multiseed_jobs,
    calculate_effective_parallel_workers,
    execute_multiseed_job_sequential,
    execute_multiseed_runs,
    execute_multiseed_runs_with_failures,
    format_parallel_progress,
    format_seed_plan,
    resolve_config_seeds,
    resolve_seed_map,
    run_multiseed_experiment,
)
from evo_system.storage.persistence_store import hash_config_snapshot
from evo_system.storage.persistence_store import PersistenceStore
from evo_system.experimentation.parallel_progress import format_active_job_progress
from evo_system.experimentation.post_multiseed_analysis import (
    ANALYSIS_DIRNAME,
    CHAMPIONS_ANALYSIS_DIRNAME,
    DEBUG_DIRNAME,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
)
from evo_system.experimentation.presets import (
    apply_preset_to_seeds,
    get_available_preset_names,
    get_preset_by_name,
)


def write_config(
    path: Path,
    *,
    extra_fields: dict | None = None,
) -> None:
    payload = {
        "mutation_seed": 42,
        "population_size": 12,
        "target_population_size": 12,
        "survivors_count": 4,
        "generations_planned": 25,
        "dataset_catalog_id": "core_1h_spot",
    }
    if extra_fields:
        payload.update(extra_fields)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_summary(config_path: Path, *, seed: int, run_id: str):
    return type(
        "Summary",
        (),
        {
            "config_name": config_path.name,
            "run_id": run_id,
            "log_file_path": config_path.with_suffix(".txt"),
            "mutation_seed": seed,
            "best_train_selection_score": 1.1,
            "final_validation_selection_score": 0.9,
            "final_validation_profit": 0.02,
            "final_validation_drawdown": 0.01,
            "final_validation_trades": 15.0,
            "best_genome_repr": "genome",
            "generation_of_best": 5,
            "train_validation_selection_gap": 0.1,
            "train_validation_profit_gap": 0.01,
            "config_path": config_path,
            "execution_status": "executed",
        },
    )()


def write_dataset_catalog(dataset_root: Path, catalog_id: str = "core_1h_spot") -> None:
    train_dir = dataset_root / catalog_id / "train" / "set_a"
    validation_dir = dataset_root / catalog_id / "validation" / "set_b"
    train_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    (train_dir / "candles.csv").write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    (validation_dir / "candles.csv").write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")


def test_cli_exposes_execution_arguments_at_top_level() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--configs-dir", "configs/runs", "--parallel-workers", "4"]
    )

    assert args.configs_dir == Path("configs/runs")
    assert args.parallel_workers == 4


def test_cli_parses_multiseed_post_analysis_arguments() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--configs-dir",
            "configs/runs",
            "--external-validation-dir",
            "data/datasets/external_validation",
            "--audit-dir",
            "data/datasets/audit",
            "--skip-post-multiseed-analysis",
        ]
    )

    assert str(args.external_validation_dir).endswith("external_validation")
    assert str(args.audit_dir).endswith("audit")
    assert args.skip_post_multiseed_analysis is True


def test_cli_defaults_to_catalog_scoped_automatic_post_analysis_resolution() -> None:
    parser = build_parser()

    args = parser.parse_args(["--configs-dir", "configs/runs"])

    assert args.external_validation_dir is None
    assert args.audit_dir is None


def test_experiment_presets_include_standard_extended_and_full() -> None:
    assert get_available_preset_names() == [
        "extended",
        "full",
        "quick",
        "screening",
        "standard",
    ]

    standard = get_preset_by_name("standard")
    extended = get_preset_by_name("extended")
    full = get_preset_by_name("full")

    assert standard is not None
    assert extended is not None
    assert full is not None

    assert standard.generations == 25
    assert standard.max_seeds == 6
    assert extended.generations == 35
    assert extended.max_seeds == 10
    assert full.generations == 50
    assert full.max_seeds == 100

    seeds = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]
    assert apply_preset_to_seeds(seeds, standard) == seeds[:6]
    assert apply_preset_to_seeds(seeds, extended) == seeds[:10]
    assert apply_preset_to_seeds(seeds, full) == seeds


def test_manifest_dataset_root_resolution_uses_data_datasets_by_default() -> None:
    assert resolve_dataset_root(DEFAULT_DATASET_ROOT) == DEFAULT_DATASET_ROOT


def test_execute_historical_run_uses_manifest_dataset_root_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_dataset_root: dict[str, Path] = {}

    class StopAfterDatasetLoad(Exception):
        pass

    def fake_load_paths(self, dataset_root: Path, dataset_catalog_id: str):
        captured_dataset_root["value"] = dataset_root
        raise StopAfterDatasetLoad

    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.DatasetPoolLoader.load_paths",
        fake_load_paths,
    )

    config_path = tmp_path / "run_balanced_manifest.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})

    with pytest.raises(StopAfterDatasetLoad):
        execute_historical_run(config_path=config_path)

    assert captured_dataset_root["value"] == DEFAULT_DATASET_ROOT


def test_execute_historical_run_persists_champion_in_new_store(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_manifest.json"
    config_snapshot = {
        "mutation_seed": 42,
        "population_size": 1,
        "target_population_size": 1,
        "survivors_count": 1,
        "generations_planned": 1,
        "dataset_catalog_id": "core_1h_spot",
        "trade_cost_rate": 0.0,
        "cost_penalty_weight": 0.25,
        "trade_count_penalty_weight": 0.0,
        "regime_filter_enabled": False,
    }
    config_path.write_text(json.dumps(config_snapshot), encoding="utf-8")

    persistence_db_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed-001",
        configs_dir_snapshot={"configs": [config_path.name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=str(tmp_path / "datasets"),
        runs_planned=1,
        runs_completed=0,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )
    run_execution_id = store.save_run_execution(
        run_execution_uid="execution-001",
        multiseed_run_id=multiseed_run_id,
        run_id="provisional-run",
        config_name=config_path.name,
        config_json_snapshot=config_snapshot,
        effective_seed=42,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="running",
    )

    train_path = tmp_path / "datasets" / "core_1h_spot" / "train" / "set_a" / "candles.csv"
    validation_path = tmp_path / "datasets" / "core_1h_spot" / "validation" / "set_b" / "candles.csv"

    genome = Genome(
        threshold_open=0.4,
        threshold_close=0.1,
        position_size=0.1,
        stop_loss=0.03,
        take_profit=0.08,
    )
    agent = Agent.create(genome)

    def fake_load_paths(self, dataset_root: Path, dataset_catalog_id: str):
        return [train_path], [validation_path]

    def fake_build_environment(*args, **kwargs):
        return args[0]

    def fake_build_initial_population(
        population_size: int,
        min_bars_between_entries: int = 0,
        entry_confirmation_bars: int = 1,
        entry_score_margin: float = 0.0,
        entry_trigger_overrides=None,
        exit_policy_overrides=None,
        trade_control_overrides=None,
        entry_trigger_constraints=None,
    ):
        return [agent]

    def fake_evaluate(self, agent, environments):
        dataset_label = str(environments[0])
        if "\\train\\" in dataset_label:
            return AgentEvaluation(
                aggregated_score=1.7,
                dispersion=0.0,
                selection_score=1.8,
                median_trades=12.0,
                median_profit=0.03,
                median_drawdown=0.01,
                dataset_scores=[1.8],
                dataset_profits=[0.03],
                dataset_drawdowns=[0.01],
                is_valid=True,
                violations=[],
                worst_dataset_score=1.8,
                bottom_quartile_score=1.8,
                score_mad=0.0,
            )
        return AgentEvaluation(
            aggregated_score=1.6,
            dispersion=0.0,
            selection_score=1.55,
            median_trades=12.0,
            median_profit=0.025,
            median_drawdown=0.01,
            dataset_scores=[1.55],
            dataset_profits=[0.025],
            dataset_drawdowns=[0.01],
            is_valid=True,
            violations=[],
            worst_dataset_score=1.55,
            bottom_quartile_score=1.55,
            score_mad=0.0,
        )

    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.DatasetPoolLoader.load_paths",
        fake_load_paths,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.build_environment",
        fake_build_environment,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.build_initial_population",
        fake_build_initial_population,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.AgentEvaluator.evaluate",
        fake_evaluate,
    )

    summary = execute_historical_run(
        config_path=config_path,
        output_dir=tmp_path / "out",
        log_name="run_manifest.txt",
        config_name_override=config_path.name,
        dataset_root=tmp_path / "datasets",
        external_validation_dir=tmp_path / "missing_external",
        persistence_db_path=persistence_db_path,
        run_execution_id=run_execution_id,
        config_json_snapshot=config_snapshot,
    )

    assert summary.run_id

    with sqlite3.connect(persistence_db_path) as connection:
        row = connection.execute(
            """
            SELECT
                run_execution_id,
                run_id,
                config_name,
                config_hash,
                champion_type,
                dataset_catalog_id,
                dataset_signature,
                config_json_snapshot
            FROM champions
            """
        ).fetchone()

    assert row is not None
    assert row[0] == run_execution_id
    assert row[1] == summary.run_id
    assert row[2] == config_path.name
    assert row[3] == hash_config_snapshot(config_snapshot)
    assert row[4] == "robust"
    assert row[5] == "core_1h_spot"
    assert row[6]
    assert '"dataset_catalog_id":"core_1h_spot"' in row[7]


def test_build_initial_population_applies_entry_trigger_overrides() -> None:
    population = build_initial_population(
        1,
        entry_trigger_overrides={
            "entry_score_threshold": 0.55,
            "min_positive_families": 3,
            "require_trend_or_breakout": True,
        },
    )

    genome = population[0].genome

    assert genome.policy_v2_enabled is True
    assert genome.entry_trigger.entry_score_threshold == 0.55
    assert genome.entry_trigger.min_positive_families == 3
    assert genome.entry_trigger.require_trend_or_breakout is True


def test_build_initial_population_applies_policy_v2_recovery_overrides() -> None:
    population = build_initial_population(
        1,
        entry_trigger_overrides={
            "entry_score_threshold": 0.43,
            "min_positive_families": 1,
            "require_trend_or_breakout": False,
        },
        exit_policy_overrides={
            "max_holding_bars": 24,
            "stop_loss_pct": 0.04,
            "take_profit_pct": 0.12,
        },
        trade_control_overrides={
            "cooldown_bars": 2,
            "min_holding_bars": 2,
            "reentry_block_bars": 2,
        },
    )

    genome = population[0].genome

    assert genome.policy_v2_enabled is True
    assert genome.entry_trigger is not None
    assert genome.exit_policy is not None
    assert genome.trade_control is not None
    assert genome.entry_trigger.entry_score_threshold == 0.43
    assert genome.entry_trigger.min_positive_families == 1
    assert genome.entry_trigger.require_trend_or_breakout is False
    assert genome.exit_policy.max_holding_bars == 24
    assert genome.exit_policy.stop_loss_pct == 0.04
    assert genome.exit_policy.take_profit_pct == 0.12
    assert genome.trade_control.cooldown_bars == 2
    assert genome.trade_control.min_holding_bars == 2
    assert genome.trade_control.reentry_block_bars == 2


def test_build_initial_population_applies_recovery_trend_constraints() -> None:
    population = build_initial_population(
        2,
        entry_trigger_constraints={
            "min_trend_weight": 0.0,
            "min_breakout_weight": 0.0,
        },
    )

    for agent in population:
        assert agent.genome.entry_trigger is not None
        assert agent.genome.entry_trigger.trend_weight >= 0.0
        assert agent.genome.entry_trigger.breakout_weight >= 0.0


def test_active_policy_v21_configs_build_population_without_legacy_threshold_dependency() -> None:
    config_names = [
        "balanced_bnb fee_5bps_fees_policy_v21_conservative.json",
        "balanced_bnb fee_5bps_fees_policy_v21_baseline.json",
        "balanced_bnb fee_5bps_fees_policy_v21_permissive.json",
        "balanced_bnb fee_5bps_fees_policy_v21_recovery.json",
        "balanced_bnb fee_5bps_fees_policy_v21_recovery_trend.json",
    ]

    for config_name in config_names:
        config = load_run_config(str(Path("configs/runs") / config_name))
        population = build_initial_population(
            8,
            entry_score_margin=config.entry_score_margin,
            min_bars_between_entries=config.min_bars_between_entries,
            entry_confirmation_bars=config.entry_confirmation_bars,
            entry_trigger_overrides=config.entry_trigger_overrides,
            exit_policy_overrides=config.exit_policy_overrides,
            trade_control_overrides=config.trade_control_overrides,
            entry_trigger_constraints=config.entry_trigger_constraints,
        )

        assert population
        assert all(
            agent.genome.policy_v2_enabled and agent.genome.entry_trigger is not None
            for agent in population
        ), config_name
        assert all(agent.genome.threshold_open == 0.0 for agent in population), config_name
        assert all(agent.genome.threshold_close == 0.0 for agent in population), config_name


def test_active_policy_v21_family_uses_expected_entry_trigger_values() -> None:
    expected_values = {
        "balanced_bnb fee_5bps_fees_policy_v21_conservative.json": (0.55, 3),
        "balanced_bnb fee_5bps_fees_policy_v21_baseline.json": (0.45, 2),
        "balanced_bnb fee_5bps_fees_policy_v21_permissive.json": (0.40, 1),
        "balanced_bnb fee_5bps_fees_policy_v21_recovery.json": (0.43, 1),
        "balanced_bnb fee_5bps_fees_policy_v21_recovery_trend.json": (0.43, 1),
    }

    for config_name, (expected_threshold, expected_positive_families) in expected_values.items():
        config = load_run_config(str(Path("configs/runs") / config_name))

        assert config.entry_trigger_overrides is not None, config_name
        assert config.entry_trigger_overrides["entry_score_threshold"] == expected_threshold, config_name
        assert config.entry_trigger_overrides["min_positive_families"] == expected_positive_families, config_name
        expected_require = not config_name.endswith("_recovery.json") and not config_name.endswith("_recovery_trend.json")
        assert config.entry_trigger_overrides["require_trend_or_breakout"] is expected_require, config_name


def test_recovery_configs_apply_trade_controls_and_trend_guardrails() -> None:
    expected_files = {
        "balanced_bnb fee_5bps_fees_policy_v21_recovery.json": False,
        "balanced_bnb fee_5bps_fees_policy_v21_recovery_trend.json": True,
    }

    for config_name, expects_constraints in expected_files.items():
        config = load_run_config(str(Path("configs/runs") / config_name))

        assert config.trade_control_overrides == {
            "cooldown_bars": 2,
            "min_holding_bars": 2,
            "reentry_block_bars": 2,
        }, config_name
        assert config.exit_policy_overrides == {
            "exit_score_threshold": 0.08,
            "exit_on_signal_reversal": True,
            "max_holding_bars": 24,
            "stop_loss_pct": 0.04,
            "take_profit_pct": 0.12,
        }, config_name
        if expects_constraints:
            assert config.entry_trigger_constraints == {
                "min_trend_weight": 0.0,
                "min_breakout_weight": 0.0,
            }, config_name
        else:
            assert config.entry_trigger_constraints is None, config_name


def test_build_multiseed_jobs_expands_config_seed_pairs(tmp_path: Path) -> None:
    config_paths = [tmp_path / "a.json", tmp_path / "b.json"]
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    seed_map = {
        config_paths[0]: [101, 102],
        config_paths[1]: [101, 102],
    }
    for config_path in config_paths:
        write_config(config_path)

    jobs = build_multiseed_jobs(
        seed_map=seed_map,
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
    )

    assert len(jobs) == 4
    assert jobs[0].config_path == config_paths[0]
    assert jobs[0].seed == 101
    assert jobs[-1].config_path == config_paths[1]
    assert jobs[-1].seed == 102


def test_effective_parallel_workers_falls_back_when_job_count_is_too_small() -> None:
    assert calculate_effective_parallel_workers(1, 4) == 1
    assert calculate_effective_parallel_workers(3, 8) == 3


def test_format_parallel_progress_is_human_readable() -> None:
    progress_line = format_parallel_progress(
        completed_jobs=3,
        total_jobs=10,
        success_count=2,
        failure_count=1,
        last_label="run_balanced seed=103",
    )

    assert progress_line == "[3/10] completed | success=2 | failed=1 | last=run_balanced seed=103"


def test_format_active_job_progress_is_human_readable() -> None:
    line = format_active_job_progress(
        {
            "config_name": "run_balanced_manifest",
            "mutation_seed": 103,
            "current_generation": 17,
            "total_generations": 40,
            "validation_selection": 0.84,
            "elapsed_seconds": 591,
        },
        fallback_label="fallback",
    )

    assert (
        line
        == "- run_balanced_manifest seed=103 | gen 17/40 | validation_selection=0.8400 | elapsed=09:51"
    )


def test_execute_multiseed_runs_keeps_sequential_run_output_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)

    def fake_execute_historical_run(**kwargs):
        calls.append(kwargs["config_name_override"])
        return build_summary(
            tmp_path / kwargs["config_name_override"],
            seed=101,
            run_id=f"run-{kwargs['config_name_override']}-101",
        )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_path = tmp_path / "a.json"
    write_config(config_path)

    summaries = execute_multiseed_runs(
        config_paths=[config_path],
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
        requested_parallel_workers=1,
    )

    assert calls == ["a.json"] * 6
    assert len(summaries) == 6


def test_execute_multiseed_runs_with_failures_collects_sequential_seed_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[int] = []
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)

    def fake_execute_historical_run(**kwargs):
        config = json.loads(kwargs["config_path"].read_text(encoding="utf-8"))
        seed = config["mutation_seed"]
        calls.append(seed)
        if seed == 102:
            raise RuntimeError("boom")
        return build_summary(tmp_path / "a.json", seed=seed, run_id=f"run-{seed}")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [101, 102, 103]})

    outcome = execute_multiseed_runs_with_failures(
        config_paths=[config_path],
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
        requested_parallel_workers=1,
    )

    assert calls == [101, 102, 103]
    assert [summary.run_id for summary in outcome.run_summaries] == ["run-101", "run-103"]
    assert outcome.failures == ["a.json seed 102: boom"]


def test_execute_multiseed_job_sequential_preserves_original_config_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    original_config_path = tmp_path / "a.json"
    write_config(original_config_path)
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    effective_config_snapshot = json.loads(original_config_path.read_text(encoding="utf-8"))
    effective_config_snapshot["mutation_seed"] = 101

    def fake_execute_historical_run(**kwargs):
        return build_summary(kwargs["config_path"], seed=101, run_id="run-001")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    summary = execute_multiseed_job_sequential(
        MultiseedJob(
            config_path=original_config_path,
            seed=101,
            output_dir=tmp_path / "out",
            dataset_root=dataset_root,
            context_name=None,
            preset_name=None,
            progress_snapshot_path=tmp_path / "progress.json",
            run_execution_uid="execution-001",
            effective_config_snapshot=effective_config_snapshot,
            dataset_catalog_id="core_1h_spot",
            dataset_signature="sig-001",
            dataset_context_json={"train_count": 1, "validation_count": 1},
            requested_dataset_root=dataset_root,
            resolved_dataset_root=dataset_root,
            execution_fingerprint="fingerprint-001",
            persistence_db_path=tmp_path / "evolution_v2.db",
        )
    )

    assert summary.config_path == original_config_path


def test_resolve_config_seeds_uses_explicit_seeds_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [201, 202, 203]})

    assert resolve_config_seeds(config_path) == [201, 202, 203]


def test_resolve_config_seeds_uses_seed_range_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seed_start": 100, "seed_count": 4})

    assert resolve_config_seeds(config_path) == [100, 101, 102, 103]


def test_resolve_config_seeds_falls_back_to_default_seed_plan(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path)

    assert resolve_config_seeds(config_path) == build_default_multiseed_seeds()


def test_resolve_seed_map_applies_presets_to_config_defined_seeds(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [201, 202, 203, 204, 205, 206, 207]})

    seed_map = resolve_seed_map([config_path], "standard")

    assert seed_map[config_path] == [201, 202, 203, 204, 205, 206]


def test_format_seed_plan_supports_per_config_seed_lists(tmp_path: Path) -> None:
    config_a = tmp_path / "a.json"
    config_b = tmp_path / "b.json"

    formatted = format_seed_plan(
        {
            config_a: [101, 102],
            config_b: [201, 202],
        }
    )

    assert formatted == "a.json: 101, 102 | b.json: 201, 202"


def test_run_multiseed_experiment_reports_effective_manifest_dataset_root(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_balanced_manifest.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        tmp_path / "evolution_v2.db",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(
            run_summaries=[],
            failures=[],
            executed_count=0,
            reused_count=0,
        ),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "out",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.write_multiseed_quick_summary",
        lambda **kwargs: tmp_path / "quick.txt",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.write_multiseed_summary",
        lambda **kwargs: tmp_path / "summary.txt",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "summary_path": tmp_path / "summary.txt",
                "quick_summary_path": tmp_path / "quick.txt",
                "champions_summary_path": tmp_path / "champions.txt",
                "analysis_dir": tmp_path / ANALYSIS_DIRNAME,
                "debug_dir": tmp_path / DEBUG_DIRNAME,
                "champions_analysis_dir": tmp_path / "analysis",
                "external_output_dir": tmp_path / "external",
                "audit_output_dir": tmp_path / "audit",
                "champion_count": 0,
                "champion_analysis_status": "skipped_no_champions",
                "external_evaluation_status": "skipped_no_champions",
                "audit_evaluation_status": "skipped_no_champions",
                "verdict": "NO_EDGE_DETECTED",
                "recommended_next_action": "Add or change signals/features before spending more time on reevaluation.",
            },
        )(),
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=DEFAULT_DATASET_ROOT,
        preset_name="screening",
        parallel_workers=1,
    )

    captured = capsys.readouterr()
    assert "Dataset root: data\\datasets" in captured.out


def test_run_multiseed_experiment_generates_post_multiseed_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        tmp_path / "evolution_v2.db",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(
            run_summaries=[build_summary(config_path, seed=42, run_id="run-001")],
            failures=[],
            executed_count=1,
            reused_count=0,
        ),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260330_120000",
    )

    def fake_run_post_multiseed_analysis(**kwargs):
        multiseed_dir = kwargs["multiseed_dir"]
        (multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME).mkdir(parents=True, exist_ok=True)
        (multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external").mkdir(parents=True, exist_ok=True)
        (multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit").mkdir(parents=True, exist_ok=True)
        (multiseed_dir / ANALYSIS_DIRNAME).mkdir(parents=True, exist_ok=True)
        (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).write_text("quick", encoding="utf-8")
        (multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME).write_text("champions", encoding="utf-8")
        return type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "analysis_dir": multiseed_dir / ANALYSIS_DIRNAME,
                "debug_dir": multiseed_dir / DEBUG_DIRNAME,
                "champions_analysis_dir": multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
                "champion_count": 0,
                "champion_analysis_status": "completed",
                "external_evaluation_status": "completed",
                "audit_evaluation_status": "completed",
                "verdict": "WEAK_PROMISING",
                "recommended_next_action": "Keep the promising patterns, then run broader external and audit batteries before scaling up.",
            },
        )()

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        fake_run_post_multiseed_analysis,
    )

    summary_path = run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=tmp_path / "datasets",
        parallel_workers=1,
    )

    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    assert summary_path == multiseed_dir / DEBUG_DIRNAME / MULTISEED_RUN_SUMMARY_NAME
    assert (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).exists()
    assert (multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME).exists()
    assert (multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME).exists()
    assert (multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external").exists()
    assert (multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit").exists()


def test_run_multiseed_experiment_persists_multiseed_and_run_executions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"seeds": [101]})

    persistence_db_path = tmp_path / "evolution_v2.db"
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        persistence_db_path,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260331_120000",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": kwargs["multiseed_dir"] / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "analysis_dir": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME,
                "debug_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME,
                "champions_analysis_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
                "champion_count": 1,
                "champion_analysis_status": "completed",
                "external_evaluation_status": "completed",
                "audit_evaluation_status": "completed",
                "verdict": "ROBUST_CANDIDATE",
                "recommended_next_action": "Promote the candidate set to a stricter friction and coverage follow-up experiment.",
            },
        )(),
    )

    def fake_execute_historical_run(**kwargs):
        return build_summary(config_path, seed=101, run_id="run-101")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=dataset_root,
        parallel_workers=1,
    )

    with sqlite3.connect(persistence_db_path) as connection:
        multiseed_row = connection.execute(
            """
            SELECT
                status,
                runs_planned,
                runs_completed,
                runs_reused,
                runs_failed,
                champions_found,
                champion_analysis_status,
                external_evaluation_status,
                audit_evaluation_status
            FROM multiseed_runs
            """
        ).fetchone()
        execution_row = connection.execute(
            """
            SELECT
                run_id,
                config_name,
                effective_seed,
                dataset_catalog_id,
                dataset_signature,
                logic_version,
                status,
                requested_dataset_root,
                resolved_dataset_root,
                log_artifact_path,
                summary_json,
                dataset_context_json,
                config_json_snapshot,
                config_hash
            FROM run_executions
            """
        ).fetchone()

    assert multiseed_row == (
        "completed",
        1,
        1,
        0,
        0,
        1,
        "completed",
        "completed",
        "completed",
    )
    assert execution_row is not None
    assert execution_row[0] == "run-101"
    assert execution_row[1] == "run_a.json"
    assert execution_row[2] == 101
    assert execution_row[3] == "core_1h_spot"
    assert execution_row[5] == CURRENT_LOGIC_VERSION
    assert execution_row[6] == "completed"
    assert execution_row[7] == dataset_root.as_posix()
    assert execution_row[8] == dataset_root.as_posix()
    assert execution_row[9].endswith("run_a.txt")
    assert '"run_id":"run-101"' in execution_row[10]
    assert '"train_count":1' in execution_row[11]
    assert '"dataset_catalog_id":"core_1h_spot"' in execution_row[12]
    effective_config_snapshot = json.loads(config_path.read_text(encoding="utf-8"))
    effective_config_snapshot["mutation_seed"] = 101
    assert execution_row[13] == hash_config_snapshot(effective_config_snapshot)


def test_run_multiseed_experiment_marks_failed_run_execution_and_uses_fingerprint_lookup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"seeds": [101]})
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)

    persistence_db_path = tmp_path / "evolution_v2.db"
    fingerprint_calls: list[str] = []

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        persistence_db_path,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260331_130000",
    )
    monkeypatch.setattr(
        "evo_system.storage.persistence_store.PersistenceStore.find_run_execution_by_fingerprint",
        lambda self, fingerprint: fingerprint_calls.append(fingerprint) or None,
    )

    def fake_execute_historical_run(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    with pytest.raises(RuntimeError, match="seed 101: boom"):
        run_multiseed_experiment(
            configs_dir=tmp_path,
            dataset_root=dataset_root,
            parallel_workers=1,
            skip_post_multiseed_analysis=True,
        )

    assert len(fingerprint_calls) == 1

    with sqlite3.connect(persistence_db_path) as connection:
        multiseed_row = connection.execute(
            """
            SELECT status, runs_planned, runs_completed, runs_reused, runs_failed
            FROM multiseed_runs
            """
        ).fetchone()
        execution_row = connection.execute(
            """
            SELECT status, failure_reason, dataset_context_json, config_json_snapshot
            FROM run_executions
            """
        ).fetchone()

    assert multiseed_row == ("completed_with_failures", 1, 0, 0, 1)
    assert execution_row is not None
    assert execution_row[0] == "failed"
    assert execution_row[1] == "boom"
    assert '"validation_count":1' in execution_row[2]
    assert '"mutation_seed":101' in execution_row[3]


def test_run_multiseed_experiment_skip_post_analysis_keeps_real_summaries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        tmp_path / "evolution_v2.db",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(
            run_summaries=[build_summary(config_path, seed=42, run_id="run-001")],
            failures=["run_a.json seed 103: boom"],
            executed_count=1,
            reused_count=0,
        ),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260330_130000",
    )

    with pytest.raises(RuntimeError, match="seed 103: boom"):
        run_multiseed_experiment(
            configs_dir=tmp_path,
            dataset_root=tmp_path / "datasets",
            parallel_workers=1,
            skip_post_multiseed_analysis=True,
        )

    multiseed_dir = tmp_path / "multiseed_20260330_130000"
    summary_text = (multiseed_dir / DEBUG_DIRNAME / MULTISEED_RUN_SUMMARY_NAME).read_text(encoding="utf-8")
    quick_text = (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "Ranking by champion rate and mean validation selection score" in summary_text
    assert "Runs: planned=6 | completed=1 | executed=1 | reused=0 | failed=1" in quick_text
    assert "Champions found:" in quick_text
    assert "Final verdict:" in quick_text
    assert "Next action:" in quick_text
    assert not (multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME).exists()


def test_run_multiseed_experiment_reuses_completed_matching_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"seeds": [101]})
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    persistence_db_path = tmp_path / "evolution_v2.db"

    store = PersistenceStore(persistence_db_path)
    store.initialize()
    prepared_job = build_multiseed_jobs(
        seed_map={config_path: [101]},
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
    )[0]
    existing_multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="existing-multiseed",
        configs_dir_snapshot={"configs": [config_path.name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=dataset_root,
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="skipped_no_champions",
        external_evaluation_status="skipped_no_champions",
        audit_evaluation_status="skipped_no_champions",
        status="completed",
    )
    store.save_run_execution(
        run_execution_uid="execution-existing",
        multiseed_run_id=existing_multiseed_run_id,
        run_id="run-101",
        config_name=config_path.name,
        config_json_snapshot=prepared_job.effective_config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature=prepared_job.dataset_signature,
        dataset_context_json=prepared_job.dataset_context_json,
        status="completed",
        requested_dataset_root=dataset_root,
        resolved_dataset_root=dataset_root,
        log_artifact_path=tmp_path / "run_a.txt",
        summary_json={
            "run_id": "run-101",
            "config_name": config_path.name,
            "mutation_seed": 101,
            "best_train_selection_score": 1.1,
            "final_validation_selection_score": 0.9,
            "final_validation_profit": 0.02,
            "final_validation_drawdown": 0.01,
            "final_validation_trades": 15.0,
            "best_genome_repr": "genome",
            "generation_of_best": 5,
            "train_validation_selection_gap": 0.1,
            "train_validation_profit_gap": 0.01,
            "log_file_path": str(tmp_path / "run_a.txt"),
            "config_path": str(config_path),
            "execution_status": "executed",
        },
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        persistence_db_path,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260331_150000",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        lambda **kwargs: pytest.fail("historical execution should have been reused"),
    )

    def fake_run_post_multiseed_analysis(**kwargs):
        multiseed_dir = kwargs["multiseed_dir"]
        (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).write_text(
            "Final verdict: WEAK_PROMISING\nNext action: Run broader external and audit batteries.\n",
            encoding="utf-8",
        )
        (multiseed_dir / ANALYSIS_DIRNAME).mkdir(parents=True, exist_ok=True)
        (multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME).write_text(
            "no champions",
            encoding="utf-8",
        )
        return type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "analysis_dir": multiseed_dir / ANALYSIS_DIRNAME,
                "debug_dir": multiseed_dir / DEBUG_DIRNAME,
                "champions_analysis_dir": multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": multiseed_dir / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
                "champion_count": 0,
                "champion_analysis_status": "skipped_no_champions",
                "external_evaluation_status": "skipped_no_champions",
                "audit_evaluation_status": "skipped_no_champions",
                "verdict": "WEAK_PROMISING",
                "recommended_next_action": "Run broader external and audit batteries.",
            },
        )()

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        fake_run_post_multiseed_analysis,
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=dataset_root,
        parallel_workers=1,
    )

    with sqlite3.connect(persistence_db_path) as connection:
        execution_count = connection.execute(
            "SELECT COUNT(*) FROM run_executions"
        ).fetchone()[0]
        latest_multiseed_row = connection.execute(
            """
            SELECT runs_planned, runs_completed, runs_reused, runs_failed
            FROM multiseed_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert execution_count == 1
    assert latest_multiseed_row == (1, 1, 1, 0)

    quick_text = (
        (tmp_path / "multiseed_20260331_150000" / MULTISEED_QUICK_SUMMARY_NAME)
        .read_text(encoding="utf-8")
    )
    assert "Final verdict: WEAK_PROMISING" in quick_text
    assert "Next action:" in quick_text


def test_failed_execution_is_not_reused_and_creates_fresh_attempt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"seeds": [101]})
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    persistence_db_path = tmp_path / "evolution_v2.db"

    store = PersistenceStore(persistence_db_path)
    store.initialize()
    prepared_job = build_multiseed_jobs(
        seed_map={config_path: [101]},
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
    )[0]
    existing_multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="existing-multiseed",
        configs_dir_snapshot={"configs": [config_path.name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=dataset_root,
        runs_planned=1,
        runs_completed=0,
        runs_reused=0,
        runs_failed=1,
        champions_found=False,
        champion_analysis_status="failed",
        external_evaluation_status="failed",
        audit_evaluation_status="failed",
        status="completed_with_failures",
    )
    store.save_run_execution(
        run_execution_uid="execution-failed",
        multiseed_run_id=existing_multiseed_run_id,
        run_id="run-failed",
        config_name=config_path.name,
        config_json_snapshot=prepared_job.effective_config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature=prepared_job.dataset_signature,
        dataset_context_json=prepared_job.dataset_context_json,
        status="failed",
        failure_reason="boom",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        persistence_db_path,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260331_160000",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": kwargs["multiseed_dir"] / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "analysis_dir": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME,
                "debug_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME,
                "champions_analysis_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
                "champion_count": 0,
                "champion_analysis_status": "skipped_no_champions",
                "external_evaluation_status": "skipped_no_champions",
                "audit_evaluation_status": "skipped_no_champions",
                "verdict": "NO_EDGE_DETECTED",
                "recommended_next_action": "Add or change signals/features before spending more time on reevaluation.",
            },
        )(),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        lambda **kwargs: build_summary(config_path, seed=101, run_id="run-new"),
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=dataset_root,
        parallel_workers=1,
    )

    with sqlite3.connect(persistence_db_path) as connection:
        status_rows = connection.execute(
            "SELECT status FROM run_executions ORDER BY id ASC"
        ).fetchall()
        latest_multiseed_row = connection.execute(
            """
            SELECT runs_planned, runs_completed, runs_reused, runs_failed
            FROM multiseed_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert [row[0] for row in status_rows] == ["failed", "completed"]
    assert latest_multiseed_row == (1, 1, 0, 0)


def test_multiseed_does_not_reuse_completed_execution_from_previous_logic_version(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"seeds": [101]})
    dataset_root = tmp_path / "datasets"
    write_dataset_catalog(dataset_root)
    persistence_db_path = tmp_path / "evolution_v2.db"

    store = PersistenceStore(persistence_db_path)
    store.initialize()
    prepared_job = build_multiseed_jobs(
        seed_map={config_path: [101]},
        output_dir=tmp_path / "out",
        dataset_root=dataset_root,
        context_name=None,
        preset_name=None,
    )[0]
    existing_multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="existing-multiseed-v6",
        configs_dir_snapshot={"configs": [config_path.name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=dataset_root,
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="skipped_no_champions",
        external_evaluation_status="skipped_no_champions",
        audit_evaluation_status="skipped_no_champions",
        status="completed",
        logic_version="v6",
    )
    store.save_run_execution(
        run_execution_uid="execution-existing-v6",
        multiseed_run_id=existing_multiseed_run_id,
        run_id="run-v6",
        config_name=config_path.name,
        config_json_snapshot=prepared_job.effective_config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature=prepared_job.dataset_signature,
        dataset_context_json=prepared_job.dataset_context_json,
        status="completed",
        logic_version="v6",
        requested_dataset_root=dataset_root,
        resolved_dataset_root=dataset_root,
        summary_json={
            "run_id": "run-v6",
            "config_name": config_path.name,
            "mutation_seed": 101,
            "best_train_selection_score": 1.1,
            "final_validation_selection_score": 0.9,
            "final_validation_profit": 0.02,
            "final_validation_drawdown": 0.01,
            "final_validation_trades": 15.0,
            "best_genome_repr": "genome",
            "generation_of_best": 5,
            "train_validation_selection_gap": 0.1,
            "train_validation_profit_gap": 0.01,
            "log_file_path": str(tmp_path / "run_v6.txt"),
            "config_path": str(config_path),
            "execution_status": "executed",
        },
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.DEFAULT_PERSISTENCE_DB_PATH",
        persistence_db_path,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260331_170000",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": kwargs["multiseed_dir"] / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "analysis_dir": kwargs["multiseed_dir"] / ANALYSIS_DIRNAME,
                "debug_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME,
                "champions_analysis_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": kwargs["multiseed_dir"] / DEBUG_DIRNAME / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
                "champion_count": 0,
                "champion_analysis_status": "skipped_no_champions",
                "external_evaluation_status": "skipped_no_champions",
                "audit_evaluation_status": "skipped_no_champions",
                "verdict": "NO_EDGE_DETECTED",
                "recommended_next_action": "Add or change signals/features before spending more time on reevaluation.",
            },
        )(),
    )

    execute_calls: list[str] = []

    def fake_execute_historical_run(**kwargs):
        execute_calls.append(kwargs["config_name_override"])
        return build_summary(config_path, seed=101, run_id="run-v7")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=dataset_root,
        parallel_workers=1,
    )

    with sqlite3.connect(persistence_db_path) as connection:
        execution_rows = connection.execute(
            "SELECT run_id, logic_version, status FROM run_executions ORDER BY id ASC"
        ).fetchall()
        latest_multiseed_row = connection.execute(
            """
            SELECT runs_planned, runs_completed, runs_reused, runs_failed
            FROM multiseed_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert execute_calls == [config_path.name]
    assert [tuple(row) for row in execution_rows] == [
        ("run-v6", "v6", "completed"),
        ("run-v7", CURRENT_LOGIC_VERSION, "completed"),
    ]
    assert latest_multiseed_row == (1, 1, 0, 0)


def test_format_effective_dataset_roots_uses_single_resolved_value() -> None:
    assert format_effective_dataset_roots([DEFAULT_DATASET_ROOT]) == "data\\datasets"
