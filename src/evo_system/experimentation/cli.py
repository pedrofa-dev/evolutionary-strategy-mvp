import argparse
from pathlib import Path

from evo_system.experimentation.batch_run import (
    CONFIGS_DIR,
    run_batch_experiment,
)
from evo_system.experimentation.multiseed_run import run_multiseed_experiment
from evo_system.experimentation.presets import get_available_preset_names
from evo_system.experimentation.single_run import (
    DEFAULT_DATASET_ROOT,
    run_single_experiment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute historical experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    single_parser = subparsers.add_parser(
        "single",
        help="Execute a single historical run.",
    )
    single_parser.add_argument(
        "--config-path",
        type=Path,
        default=Path("configs/run_config.json"),
        help="Path to the run config JSON.",
    )
    single_parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory.",
    )
    single_parser.add_argument(
        "--preset",
        type=str,
        choices=get_available_preset_names(),
        default=None,
        help="Optional execution preset overriding generations only.",
    )

    batch_parser = subparsers.add_parser(
        "batch",
        help="Execute all run configs in a directory.",
    )
    batch_parser.add_argument(
        "--configs-dir",
        type=Path,
        default=CONFIGS_DIR,
        help="Directory containing run config JSON files.",
    )
    batch_parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory.",
    )

    multiseed_parser = subparsers.add_parser(
        "multiseed",
        help="Execute all run configs across multiple mutation seeds.",
    )
    multiseed_parser.add_argument(
        "--configs-dir",
        type=Path,
        default=CONFIGS_DIR,
        help="Directory containing run config JSON files.",
    )
    multiseed_parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory.",
    )
    multiseed_parser.add_argument(
        "--preset",
        type=str,
        choices=get_available_preset_names(),
        default=None,
        help="Optional execution preset overriding generations and seeds/max_seeds.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "single":
        run_single_experiment(
            config_path=args.config_path,
            dataset_root=args.dataset_root,
            preset_name=args.preset,
        )
        return

    if args.command == "batch":
        run_batch_experiment(
            configs_dir=args.configs_dir,
            dataset_root=args.dataset_root,
        )
        return

    if args.command == "multiseed":
        run_multiseed_experiment(
            configs_dir=args.configs_dir,
            dataset_root=args.dataset_root,
            preset_name=args.preset,
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")
