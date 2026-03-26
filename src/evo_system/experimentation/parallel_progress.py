import json
from pathlib import Path


PROGRESS_POLL_INTERVAL_SECONDS = 5.0


def write_progress_snapshot(
    snapshot_path: Path,
    *,
    config_name: str,
    mutation_seed: int | None,
    current_generation: int,
    total_generations: int,
    validation_selection: float | None,
    elapsed_seconds: float,
) -> None:
    snapshot = {
        "config_name": config_name,
        "mutation_seed": mutation_seed,
        "current_generation": current_generation,
        "total_generations": total_generations,
        "validation_selection": validation_selection,
        "elapsed_seconds": elapsed_seconds,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")


def read_progress_snapshot(snapshot_path: Path) -> dict | None:
    if not snapshot_path.exists():
        return None

    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def format_elapsed_seconds(elapsed_seconds: float) -> str:
    total_seconds = max(0, int(elapsed_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_active_job_progress(
    snapshot: dict | None,
    *,
    fallback_label: str,
) -> str:
    if snapshot is None:
        return f"- {fallback_label} | progress=starting"

    current_generation = snapshot.get("current_generation", 0)
    total_generations = snapshot.get("total_generations", 0)
    validation_selection = snapshot.get("validation_selection")
    elapsed_seconds = snapshot.get("elapsed_seconds", 0.0)
    label = snapshot.get("config_name") or fallback_label
    mutation_seed = snapshot.get("mutation_seed")

    if mutation_seed is not None:
        label = f"{label} seed={mutation_seed}"

    if validation_selection is None:
        selection_text = "validation_selection=n/a"
    else:
        selection_text = f"validation_selection={validation_selection:.4f}"

    return (
        f"- {label} | "
        f"gen {current_generation}/{total_generations} | "
        f"{selection_text} | "
        f"elapsed={format_elapsed_seconds(float(elapsed_seconds))}"
    )
