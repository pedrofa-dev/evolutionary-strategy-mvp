from pathlib import Path
import sqlite3

from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.storage.sqlite_store import SQLiteStore


def test_initialize_creates_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    assert database_path.exists()


def test_initialize_creates_indexes_for_champion_queries(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
            ORDER BY name
            """
        )
        index_names = [row[0] for row in cursor.fetchall()]

    assert "idx_champions_config_name" in index_names
    assert "idx_champions_run_id" in index_names


def test_save_and_load_generation_result(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    agent = Agent.create(
        Genome(
            threshold_open=0.8,
            threshold_close=0.4,
            position_size=0.2,
            stop_loss=0.05,
            take_profit=0.1,
        )
    )

    generation_result = GenerationResult(
        generation_number=1,
        evaluated_agents=[(agent, 0.75)],
        best_fitness=0.75,
        average_fitness=0.75,
    )

    store = SQLiteStore(str(database_path))
    store.initialize()
    store.save_generation_result("run-001", generation_result)

    loaded = store.load_generation_result("run-001", 1)

    assert loaded is not None
    assert loaded["generation_number"] == 1
    assert loaded["best_fitness"] == 0.75
    assert loaded["average_fitness"] == 0.75
    assert len(loaded["evaluated_agents"]) == 1
    assert loaded["evaluated_agents"][0]["fitness"] == 0.75


def test_save_run_record(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    run_record = RunRecord(
        run_id="run-001",
        mutation_seed=42,
        population_size=4,
        target_population_size=4,
        survivors_count=2,
        generations_planned=5,
    )

    store.save_run_record(run_record)

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                run_id,
                mutation_seed,
                population_size,
                target_population_size,
                survivors_count,
                generations_planned
            FROM runs
            WHERE run_id = ?
            """,
            ("run-001",),
        )
        loaded = cursor.fetchone()

    assert loaded is not None
    assert loaded[0] == "run-001"
    assert loaded[1] == 42
    assert loaded[2] == 4
    assert loaded[3] == 4
    assert loaded[4] == 2
    assert loaded[5] == 5


def test_save_and_load_champion(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
        use_momentum=True,
        momentum_threshold=0.001,
        use_trend=False,
        trend_threshold=0.0,
        trend_window=5,
        use_exit_momentum=False,
        exit_momentum_threshold=0.0,
        ret_short_window=3,
        ret_mid_window=12,
        ma_window=20,
        range_window=20,
        vol_short_window=5,
        vol_long_window=20,
        weight_ret_short=0.8,
        weight_ret_mid=0.2,
        weight_dist_ma=-0.4,
        weight_range_pos=0.3,
        weight_vol_ratio=-0.5,
    )

    metrics = {
        "train_selection": 1.9,
        "validation_selection": 1.7,
        "selection_gap": 0.2,
        "validation_profit": 0.0021,
        "validation_drawdown": 0.0012,
        "validation_trades": 11,
        "dispersion": 0.15,
        "mad": 0.08,
        "worst_dataset": 1.4,
    }

    store.save_champion(
        run_id="run-001",
        generation_number=5,
        mutation_seed=42,
        config_name="baseline_stable",
        genome=genome,
        metrics=metrics,
    )

    loaded = store.load_champions()

    assert len(loaded) == 1

    champion = loaded[0]

    assert champion["run_id"] == "run-001"
    assert champion["generation_number"] == 5
    assert champion["mutation_seed"] == 42
    assert champion["config_name"] == "baseline_stable"

    assert champion["genome"]["threshold_open"] == 0.8
    assert champion["genome"]["threshold_close"] == 0.4
    assert champion["genome"]["use_momentum"] is True
    assert champion["genome"]["weight_ret_short"] == 0.8

    assert champion["metrics"]["validation_selection"] == 1.7
    assert champion["metrics"]["validation_profit"] == 0.0021
    assert champion["metrics"]["validation_drawdown"] == 0.0012
    assert champion["metrics"]["validation_trades"] == 11


def test_load_champions_can_filter_by_run_id(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    metrics = {
        "validation_selection": 1.7,
        "validation_profit": 0.0021,
        "validation_drawdown": 0.0012,
        "validation_trades": 11,
        "selection_gap": 0.2,
    }

    store.save_champion(
        run_id="run-001",
        generation_number=5,
        mutation_seed=42,
        config_name="config_a",
        genome=genome,
        metrics=metrics,
    )

    store.save_champion(
        run_id="run-002",
        generation_number=6,
        mutation_seed=43,
        config_name="config_b",
        genome=genome,
        metrics=metrics,
    )

    loaded = store.load_champions(run_id="run-001")

    assert len(loaded) == 1
    assert loaded[0]["run_id"] == "run-001"
    assert loaded[0]["config_name"] == "config_a"
