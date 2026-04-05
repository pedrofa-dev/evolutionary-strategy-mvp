import json
from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import Genome
from evo_system.experimental_space.identity import build_runtime_component_fingerprint
from evo_system.experimentation.historical_run import execute_historical_run
from evo_system.storage import PersistenceStore, RunReadRepository
from evo_system.storage.run_read_cli import main as run_read_cli_main


def build_summary_payload(run_id: str, *, include_snapshot: bool = True) -> dict:
    snapshot = (
        {
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "standard",
        }
        if include_snapshot
        else None
    )
    return {
        "run_id": run_id,
        "config_name": "run_a.json",
        "mutation_seed": 101,
        "best_train_selection_score": 1.8,
        "final_validation_selection_score": 1.55,
        "final_validation_profit": 0.025,
        "final_validation_drawdown": 0.01,
        "final_validation_trades": 12.0,
        "best_genome_repr": "Genome(...)",
        "generation_of_best": 5,
        "train_validation_selection_gap": 0.25,
        "train_validation_profit_gap": 0.005,
        "config_path": "configs/runs/run_a.json",
        "execution_status": "executed",
        "experimental_space_snapshot": snapshot,
    }


def seed_run(
    database_path: Path,
    *,
    run_id: str,
    with_champion: bool = True,
    include_snapshot: bool = True,
    include_modular_config_fields: bool = True,
    config_snapshot_overrides: dict | None = None,
) -> None:
    store = PersistenceStore(database_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=f"multiseed-{run_id}",
        configs_dir_snapshot={"configs": ["run_a.json"]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=with_champion,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )
    config_snapshot = {
        "mutation_seed": 101,
        "population_size": 12,
        "target_population_size": 12,
        "survivors_count": 4,
        "generations_planned": 25,
        "dataset_catalog_id": "core_1h_spot",
    }
    if include_modular_config_fields:
        config_snapshot["market_mode_name"] = "spot"
        config_snapshot["leverage"] = 1.0
    if config_snapshot_overrides:
        config_snapshot.update(config_snapshot_overrides)
    experimental_space_snapshot = (
        {
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "standard",
        }
        if include_snapshot
        else None
    )
    run_execution_id = store.save_run_execution(
        run_execution_uid=f"execution-{run_id}",
        multiseed_run_id=multiseed_run_id,
        run_id=run_id,
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature=f"sig-{run_id}",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
        summary_json=build_summary_payload(run_id, include_snapshot=include_snapshot),
        experimental_space_snapshot_json=experimental_space_snapshot,
    )

    if with_champion:
        store.save_champion(
            champion_uid=f"champion-{run_id}",
            run_execution_id=run_execution_id,
            run_id=run_id,
            config_name="run_a.json",
            config_json_snapshot=config_snapshot,
            generation_number=5,
            mutation_seed=101,
            champion_type="robust",
            genome_json_snapshot=Genome(
                threshold_open=0.4,
                threshold_close=0.1,
                position_size=0.1,
                stop_loss=0.03,
                take_profit=0.08,
            ).to_dict(),
            experimental_space_snapshot_json=experimental_space_snapshot,
            dataset_catalog_id="core_1h_spot",
            dataset_signature=f"sig-{run_id}",
            train_metrics_json={
                "selection_score": 1.8,
                "median_profit": 0.03,
                "median_drawdown": 0.01,
                "median_trades": 12.0,
                "dataset_scores": [1.8],
                "dataset_profits": [0.03],
                "dataset_drawdowns": [0.01],
                "violations": [],
                "is_valid": True,
            },
            validation_metrics_json={
                "selection_score": 1.55,
                "median_profit": 0.025,
                "median_drawdown": 0.01,
                "median_trades": 12.0,
                "dispersion": 0.0,
                "dataset_scores": [1.55],
                "dataset_profits": [0.025],
                "dataset_drawdowns": [0.01],
                "violations": [],
                "is_valid": True,
            },
            champion_metrics_json={"selection_gap": 0.25},
        )


def test_run_read_repository_lists_and_reads_runs(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(database_path, run_id="run-001")
    seed_run(database_path, run_id="run-002", with_champion=False)

    repository = RunReadRepository(database_path)

    runs = repository.list_runs(limit=10)
    assert [item.run_id for item in runs] == ["run-002", "run-001"]
    assert runs[0].champion_persisted is False
    assert runs[1].stack_label.startswith("signal_pack=policy_v21_default")
    assert runs[1].runtime_component_fingerprint is not None
    assert runs[1].market_mode_name == "spot"
    assert runs[1].leverage == 1.0

    summary = repository.get_run_summary("run-001")
    assert summary is not None
    assert summary.run_id == "run-001"
    assert summary.config_name == "run_a.json"
    assert summary.dataset_catalog_id == "core_1h_spot"
    assert summary.config_json_snapshot["dataset_catalog_id"] == "core_1h_spot"
    assert summary.final_validation_selection_score == 1.55
    assert summary.best_genome_generation == 5
    assert summary.champion_persisted is True
    assert summary.runtime_component_fingerprint == build_runtime_component_fingerprint(
        summary.experimental_space_snapshot
    )
    assert summary.market_mode_name == "spot"
    assert summary.leverage == 1.0
    assert summary.train_breakdown is not None
    assert summary.train_breakdown.dataset_scores == [1.8]
    assert summary.best_genome is not None
    assert summary.best_genome.genome_snapshot is not None


def test_run_read_repository_handles_missing_optional_metadata_safely(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(
        database_path,
        run_id="run-legacy",
        with_champion=False,
        include_snapshot=False,
        include_modular_config_fields=False,
    )

    repository = RunReadRepository(database_path)
    summary = repository.get_run_summary("run-legacy")

    assert summary is not None
    assert summary.stack_label == "unknown"
    assert summary.best_genome is not None
    assert summary.best_genome.genome_snapshot is None
    assert summary.best_genome.genome_repr == "Genome(...)"
    assert summary.experimental_space_snapshot is None
    train_breakdown, validation_breakdown = repository.get_train_validation_breakdowns("run-legacy")
    assert train_breakdown is None
    assert validation_breakdown is None


def test_run_read_repository_list_runs_reconstructs_stack_when_modular_config_fields_are_explicit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(
        database_path,
        run_id="run-futures-legacy",
        with_champion=False,
        include_snapshot=False,
        include_modular_config_fields=False,
        config_snapshot_overrides={
            "market_mode_name": "futures",
            "leverage": 1.0,
        },
    )

    repository = RunReadRepository(database_path)
    runs = repository.list_runs(limit=5)

    assert len(runs) == 1
    assert runs[0].run_id == "run-futures-legacy"
    assert runs[0].market_mode_name == "futures"
    assert runs[0].leverage == 1.0
    assert runs[0].stack_label.startswith(
        "signal_pack=policy_v21_default | genome_schema=policy_v2_default"
    )


def test_run_read_repository_reconstructs_stack_from_explicit_modular_config_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(
        database_path,
        run_id="run-modular-config",
        with_champion=False,
        include_snapshot=False,
        config_snapshot_overrides={
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "modular_genome_v1",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "market_mode_name": "spot",
            "leverage": 1.0,
        },
    )

    repository = RunReadRepository(database_path)
    summary = repository.get_run_summary("run-modular-config")

    assert summary is not None
    assert summary.experimental_space_snapshot is not None
    assert summary.experimental_space_snapshot["signal_pack_name"] == "policy_v21_default"
    assert summary.stack_label.startswith("signal_pack=policy_v21_default")


def test_run_read_cli_lists_and_shows_run_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(database_path, run_id="run-001")

    monkeypatch.setattr(
        "sys.argv",
        ["read_runs.py", "--db-path", str(database_path), "--limit", "5"],
    )
    run_read_cli_main()
    output = capsys.readouterr().out
    assert "run-001 | config=run_a.json" in output

    monkeypatch.setattr(
        "sys.argv",
        ["read_runs.py", "--db-path", str(database_path), "--run-id", "run-001"],
    )
    run_read_cli_main()
    output = capsys.readouterr().out
    assert "Run ID: run-001" in output
    assert "Execution fingerprint:" in output
    assert "Runtime component fingerprint:" in output
    assert "Logic version:" in output
    assert "Market mode: spot" in output
    assert "Leverage: 1.0" in output
    assert "Champion persisted: True" in output


def test_run_read_repository_uses_readonly_sqlite_connection(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    seed_run(database_path, run_id="run-001")

    repository = RunReadRepository(database_path)
    summary = repository.get_run_summary("run-001")

    assert summary is not None

    with repository._connect_readonly() as connection:
        try:
            connection.execute("CREATE TABLE should_fail (id INTEGER)")
        except Exception as exc:
            assert "readonly" in str(exc).lower() or "read-only" in str(exc).lower()
        else:
            raise AssertionError("RunReadRepository unexpectedly allowed writes")


def test_run_read_repository_reads_persisted_run_without_reexecution(
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

    repository = RunReadRepository(persistence_db_path)
    persisted = repository.get_run_summary("provisional-run")

    assert persisted is not None
    assert persisted.run_id == "provisional-run"
    assert persisted.champion_persisted is True
    assert persisted.execution_fingerprint
    assert persisted.best_genome is not None
    assert persisted.best_genome.genome_snapshot is not None
    assert persisted.validation_breakdown is not None
    assert persisted.validation_breakdown.selection_score == 1.55
