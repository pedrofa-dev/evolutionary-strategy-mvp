from pathlib import Path

from evo_system.orchestration.config_loader import load_run_config


DEFAULT_DATASET_ROOT = Path("data/processed")
DEFAULT_MANIFEST_DATASET_ROOT = Path("data/datasets")


def resolve_dataset_root(
    requested_dataset_root: Path,
    dataset_mode: str,
) -> Path:
    if (
        dataset_mode == "manifest"
        and requested_dataset_root == DEFAULT_DATASET_ROOT
    ):
        return DEFAULT_MANIFEST_DATASET_ROOT

    return requested_dataset_root


def resolve_effective_dataset_roots(
    config_paths: list[Path],
    requested_dataset_root: Path,
) -> list[Path]:
    effective_roots = {
        resolve_dataset_root(
            requested_dataset_root=requested_dataset_root,
            dataset_mode=load_run_config(str(config_path)).dataset_mode,
        )
        for config_path in config_paths
    }
    return sorted(effective_roots)


def format_effective_dataset_roots(effective_roots: list[Path]) -> str:
    if not effective_roots:
        return "none"

    if len(effective_roots) == 1:
        return str(effective_roots[0])

    return ", ".join(str(path) for path in effective_roots)
