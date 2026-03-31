import argparse
from pathlib import Path

from evo_system.experimentation.dataset_roots import DEFAULT_DATASET_ROOT
from evo_system.experimentation.multiseed_run import CONFIGS_DIR, run_multiseed_experiment
from evo_system.experimentation.presets import get_available_preset_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute historical experiments across multiple mutation seeds.",
    )
    parser.add_argument(
        "--configs-dir",
        type=Path,
        default=CONFIGS_DIR,
        help="Directory containing run config JSON files.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory for manifest catalogs. Default: data/datasets.",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=get_available_preset_names(),
        default=None,
        help="Optional execution preset overriding generations and seeds/max_seeds.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Number of worker processes for independent runs. Default: 1.",
    )
    parser.add_argument(
        "--external-validation-dir",
        type=Path,
        default=None,
        help="Optional direct directory overriding automatic catalog-scoped external validation datasets.",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=None,
        help="Optional direct directory overriding automatic catalog-scoped audit datasets.",
    )
    parser.add_argument(
        "--skip-post-multiseed-analysis",
        action="store_true",
        help="Skip automatic post-multiseed champion analysis and reevaluation.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    run_multiseed_experiment(
        configs_dir=args.configs_dir,
        dataset_root=args.dataset_root,
        preset_name=args.preset,
        parallel_workers=args.parallel_workers,
        external_validation_dir=args.external_validation_dir,
        audit_dir=args.audit_dir,
        skip_post_multiseed_analysis=args.skip_post_multiseed_analysis,
    )
