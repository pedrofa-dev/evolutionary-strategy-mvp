from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evo_system.experimental_space.registry import NamedRegistry


@dataclass(frozen=True)
class ExperimentPreset:
    name: str
    generations: int
    max_seeds: int | None = None
    seeds: list[int] | None = None


PRESET_QUICK = ExperimentPreset(
    name="quick",
    generations=10,
    max_seeds=2,
)

PRESET_SCREENING = ExperimentPreset(
    name="screening",
    generations=15,
    max_seeds=4,
)

PRESET_STANDARD = ExperimentPreset(
    name="standard",
    generations=25,
    max_seeds=6,
)

PRESET_EXTENDED = ExperimentPreset(
    name="extended",
    generations=35,
    max_seeds=10,
)

PRESET_FULL = ExperimentPreset(
    name="full",
    generations=50,
    max_seeds=100,
)

PRESET_REGISTRY: NamedRegistry[ExperimentPreset] = NamedRegistry()
PRESET_REGISTRY.register(PRESET_QUICK.name, PRESET_QUICK)
PRESET_REGISTRY.register(PRESET_SCREENING.name, PRESET_SCREENING)
PRESET_REGISTRY.register(PRESET_STANDARD.name, PRESET_STANDARD)
PRESET_REGISTRY.register(PRESET_EXTENDED.name, PRESET_EXTENDED)
PRESET_REGISTRY.register(PRESET_FULL.name, PRESET_FULL)

PRESET_DESCRIPTIONS = {
    "quick": "Runtime multiseed preset for very fast local iteration.",
    "screening": "Runtime multiseed preset for lightweight candidate screening.",
    "standard": "Runtime multiseed preset for balanced day-to-day evaluation.",
    "extended": "Runtime multiseed preset for broader evaluation before promotion.",
    "full": "Runtime multiseed preset for the heaviest built-in evaluation budget.",
}


def get_available_preset_names() -> list[str]:
    return PRESET_REGISTRY.list_names()


def describe_preset(name: str) -> str:
    return PRESET_DESCRIPTIONS.get(
        name,
        "Runtime multiseed preset used to shape generation and seed budgets.",
    )


def get_preset_by_name(name: str | None) -> ExperimentPreset | None:
    if name is None:
        return None
    try:
        return PRESET_REGISTRY.get(name.lower())
    except KeyError:
        return None


def serialize_preset(preset: ExperimentPreset | None) -> dict[str, Any] | None:
    if preset is None:
        return None

    return {
        "name": preset.name,
        "generations": preset.generations,
        "max_seeds": preset.max_seeds,
        "seeds": list(preset.seeds) if preset.seeds is not None else None,
    }


def deserialize_preset(payload: dict[str, Any] | None) -> ExperimentPreset | None:
    if payload is None:
        return None
    return get_preset_by_name(payload.get("name"))


def apply_preset_to_config_data(
    config_data: dict[str, Any],
    preset: ExperimentPreset | None,
) -> dict[str, Any]:
    updated = dict(config_data)

    if preset is None:
        return updated

    updated["generations_planned"] = preset.generations

    if preset.seeds is not None:
        updated["seeds"] = list(preset.seeds)

    if preset.max_seeds is not None:
        updated["max_seeds"] = preset.max_seeds

    return updated


def apply_preset_to_seeds(
    seeds: list[int],
    preset: ExperimentPreset | None,
) -> list[int]:
    if preset is None:
        return list(seeds)

    if preset.seeds is not None:
        return list(preset.seeds)

    if preset.max_seeds is not None:
        return list(seeds[: preset.max_seeds])

    return list(seeds)
