from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunConfig:
    mutation_seed: int | None
    population_size: int
    target_population_size: int
    survivors_count: int
    generations_planned: int

    def validate(self) -> None:
        if self.population_size <= 0:
            raise ValueError("population_size must be greater than 0")

        if self.target_population_size <= 0:
            raise ValueError("target_population_size must be greater than 0")

        if self.survivors_count <= 0:
            raise ValueError("survivors_count must be greater than 0")

        if self.generations_planned <= 0:
            raise ValueError("generations_planned must be greater than 0")

        if self.target_population_size < self.survivors_count:
            raise ValueError("target_population_size cannot be smaller than survivors_count")

        if self.population_size < self.survivors_count:
            raise ValueError("population_size cannot be smaller than survivors_count")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_seed": self.mutation_seed,
            "population_size": self.population_size,
            "target_population_size": self.target_population_size,
            "survivors_count": self.survivors_count,
            "generations_planned": self.generations_planned,
        }