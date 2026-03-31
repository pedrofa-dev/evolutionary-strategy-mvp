from pathlib import Path

DEFAULT_DATASET_ROOT = Path("data/datasets")


def resolve_dataset_root(requested_dataset_root: Path) -> Path:
    return requested_dataset_root


def resolve_effective_dataset_roots(
    config_paths: list[Path],
    requested_dataset_root: Path,
) -> list[Path]:
    effective_roots = {resolve_dataset_root(requested_dataset_root)}
    return sorted(effective_roots)


def format_effective_dataset_roots(effective_roots: list[Path]) -> str:
    if not effective_roots:
        return "none"

    if len(effective_roots) == 1:
        return str(effective_roots[0])

    return ", ".join(str(path) for path in effective_roots)
