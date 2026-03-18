from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evo_system.domain.agent import Agent


@dataclass(frozen=True)
class GenerationResult:
    generation_number: int
    evaluated_agents: list[tuple[Agent, float]]
    best_fitness: float
    average_fitness: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_number": self.generation_number,
            "evaluated_agents": [
                {
                    "agent": agent.to_dict(),
                    "fitness": fitness,
                }
                for agent, fitness in self.evaluated_agents
            ],
            "best_fitness": self.best_fitness,
            "average_fitness": self.average_fitness,
        }