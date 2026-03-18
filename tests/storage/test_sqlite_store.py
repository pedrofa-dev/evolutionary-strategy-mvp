from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome
from evo_system.storage.sqlite_store import SQLiteStore
from evo_system.domain.run_record import RunRecord


def test_initialize_creates_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "test_evolution.db"

    store = SQLiteStore(str(database_path))
    store.initialize()

    assert database_path.exists()


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
    store.save_generation_result("run-001",generation_result)

    loaded = store.load_generation_result("run-001",1)

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

    loaded = None
    import sqlite3
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            SELECT run_id, mutation_seed, population_size, target_population_size, survivors_count, generations_planned
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