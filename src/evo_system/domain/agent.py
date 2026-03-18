from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import uuid

from evo_system.domain.genome import Genome


@dataclass(frozen=True)
class Agent:
    id: str
    genome: Genome

    @staticmethod
    def create(genome: Genome) -> "Agent":
        """
        Factory method to create a new agent with a unique id.
        """
        return Agent(
            id=str(uuid.uuid4()),
            genome=genome,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "genome": self.genome.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Agent":
        return cls(
            id=str(data["id"]),
            genome=Genome.from_dict(data["genome"]),
        )