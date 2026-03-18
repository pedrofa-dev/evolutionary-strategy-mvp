from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from evo_system.domain.generation_result import GenerationResult


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