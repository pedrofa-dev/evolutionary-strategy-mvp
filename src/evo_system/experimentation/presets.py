from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExperimentPreset:
    name: str
    generations: int
    max_seeds: int | None = None
    seeds: list[int] | None = None


PRESET_QUICK = ExperimentPreset(
    name="quick",
    generations=10,
    max_seeds=1,
)

PRESET_SCREENING = ExperimentPreset(
    name="screening",
    generations=15,
    max_seeds=3,
)

PRESET_FULL = ExperimentPreset(
    name="full",
    generations=25,
    max_seeds=5,
)

PRESETS_BY_NAME = {
    PRESET_QUICK.name: PRESET_QUICK,
    PRESET_SCREENING.name: PRESET_SCREENING,
    PRESET_FULL.name: PRESET_FULL,
}


def get_available_preset_names() -> list[str]:
    return sorted(PRESETS_BY_NAME.keys())


def get_preset_by_name(name: str | None) -> ExperimentPreset | None:
    if name is None:
        return None
    return PRESETS_BY_NAME.get(name.lower())


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
