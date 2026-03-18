from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    mutation_seed: int | None
    population_size: int
    target_population_size: int
    survivors_count: int
    generations_planned: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mutation_seed": self.mutation_seed,
            "population_size": self.population_size,
            "target_population_size": self.target_population_size,
            "survivors_count": self.survivors_count,
            "generations_planned": self.generations_planned,
        }