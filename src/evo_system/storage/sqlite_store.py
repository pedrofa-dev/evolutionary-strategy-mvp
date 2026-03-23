from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord


class SQLiteStore:
    def __init__(self, database_path: str = "data/evolution.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_results (
                    run_id TEXT NOT NULL,
                    generation_number INTEGER NOT NULL,
                    best_fitness REAL NOT NULL,
                    average_fitness REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, generation_number)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    mutation_seed INTEGER,
                    population_size INTEGER NOT NULL,
                    target_population_size INTEGER NOT NULL,
                    survivors_count INTEGER NOT NULL,
                    generations_planned INTEGER NOT NULL,
                    run_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS champions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    generation_number INTEGER,
                    mutation_seed INTEGER,
                    config_name TEXT,
                    genome_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def save_generation_result(self, run_id: str, result: GenerationResult) -> None:
        payload = json.dumps(result.to_dict())

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO generation_results (
                    run_id,
                    generation_number,
                    best_fitness,
                    average_fitness,
                    result_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result.generation_number,
                    result.best_fitness,
                    result.average_fitness,
                    payload,
                ),
            )
            connection.commit()

    def save_run_record(self, run_record: RunRecord) -> None:
        payload = json.dumps(run_record.to_dict())

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id,
                    mutation_seed,
                    population_size,
                    target_population_size,
                    survivors_count,
                    generations_planned,
                    run_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_record.run_id,
                    run_record.mutation_seed,
                    run_record.population_size,
                    run_record.target_population_size,
                    run_record.survivors_count,
                    run_record.generations_planned,
                    payload,
                ),
            )
            connection.commit()

    def save_champion(
        self,
        run_id: str,
        generation_number: int | None,
        mutation_seed: int | None,
        config_name: str | None,
        genome: Genome,
        metrics: dict[str, Any],
    ) -> None:
        genome_payload = json.dumps(genome.to_dict())
        metrics_payload = json.dumps(metrics)

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO champions (
                    run_id,
                    generation_number,
                    mutation_seed,
                    config_name,
                    genome_json,
                    metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    generation_number,
                    mutation_seed,
                    config_name,
                    genome_payload,
                    metrics_payload,
                ),
            )
            connection.commit()

    def load_generation_result(self, run_id: str, generation_number: int) -> dict | None:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                SELECT result_json
                FROM generation_results
                WHERE run_id = ? AND generation_number = ?
                """,
                (run_id, generation_number),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return json.loads(row[0])

    def load_champions(self, run_id: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT
                id,
                run_id,
                generation_number,
                mutation_seed,
                config_name,
                genome_json,
                metrics_json,
                created_at
            FROM champions
        """
        parameters: tuple[Any, ...] = ()

        if run_id is not None:
            query += " WHERE run_id = ?"
            parameters = (run_id,)

        query += " ORDER BY id ASC"

        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(query, parameters)
            rows = cursor.fetchall()

        champions: list[dict[str, Any]] = []

        for row in rows:
            champions.append(
                {
                    "id": row[0],
                    "run_id": row[1],
                    "generation_number": row[2],
                    "mutation_seed": row[3],
                    "config_name": row[4],
                    "genome": json.loads(row[5]),
                    "metrics": json.loads(row[6]),
                    "created_at": row[7],
                }
            )

        return champions