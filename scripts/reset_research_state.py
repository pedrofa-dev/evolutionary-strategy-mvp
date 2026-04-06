from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DB_PATH = REPO_ROOT / "data" / "evolution_v2.db"
LEGACY_DB_PATH = REPO_ROOT / "data" / "evolution.db"
MULTISEED_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "multiseed"
RUN_LAB_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "ui_run_lab"
ANALYSIS_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "analysis"
LEGACY_RUNS_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "runs"
LEGACY_BATCHES_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "batches"


@dataclass(frozen=True)
class ResetTarget:
    path: Path
    kind: str
    reason: str
    optional: bool = False


@dataclass(frozen=True)
class ResetPlan:
    mode: str
    destructive: bool
    targets: tuple[ResetTarget, ...]
    preserved_paths: tuple[str, ...]
    notes: tuple[str, ...]


def build_reset_plan(
    *,
    repo_root: Path = REPO_ROOT,
    mode: str,
    include_legacy_db: bool = False,
    include_legacy_artifacts: bool = False,
    destructive: bool = False,
) -> ResetPlan:
    targets: list[ResetTarget] = [
        ResetTarget(
            path=repo_root / "data" / "evolution_v2.db",
            kind="file",
            reason="Canonical SQLite research history database.",
        ),
        ResetTarget(
            path=repo_root / "artifacts" / "multiseed",
            kind="directory",
            reason="Canonical multiseed campaign artifacts and summaries.",
        ),
        ResetTarget(
            path=repo_root / "artifacts" / "ui_run_lab",
            kind="directory",
            reason="Run Lab staging outputs and temporary config-set copies.",
        ),
    ]

    notes = [
        "Dry-run is the default. Pass --execute to perform deletions.",
        "Active run configs under configs/runs/ are preserved by default.",
        "Dataset manifests, built datasets, and market data are preserved.",
    ]

    if mode == "hard":
        targets.append(
            ResetTarget(
                path=repo_root / "artifacts" / "analysis",
                kind="directory",
                reason="Manual analysis and reevaluation outputs derived from older research state.",
            )
        )

    if include_legacy_db:
        targets.append(
            ResetTarget(
                path=repo_root / "data" / "evolution.db",
                kind="file",
                reason="Legacy or historical database file present on disk but not part of the active canonical workflow.",
                optional=True,
            )
        )
        notes.append(
            "Legacy database cleanup was explicitly requested via --include-legacy-db."
        )

    if include_legacy_artifacts:
        targets.extend(
            [
                ResetTarget(
                    path=repo_root / "artifacts" / "runs",
                    kind="directory",
                    reason="Historical or compatibility-oriented run logs outside the main multiseed lane.",
                    optional=True,
                ),
                ResetTarget(
                    path=repo_root / "artifacts" / "batches",
                    kind="directory",
                    reason="Batch artifacts not treated as part of the canonical reset path by default.",
                    optional=True,
                ),
            ]
        )
        notes.append(
            "Legacy artifact cleanup was explicitly requested via --include-legacy-artifacts."
        )

    preserved_paths = (
        "configs/runs/",
        "configs/datasets/",
        "data/market_data/",
        "data/datasets/",
        "src/",
        "docs/",
        "tests/",
        "src/evo_system/experimental_space/assets/",
    )

    return ResetPlan(
        mode=mode,
        destructive=destructive,
        targets=tuple(targets),
        preserved_paths=preserved_paths,
        notes=tuple(notes),
    )


def format_reset_plan(plan: ResetPlan) -> str:
    lines = [
        f"Research reset mode: {plan.mode}",
        f"Execution mode: {'execute' if plan.destructive else 'dry-run'}",
        "",
        "Targets to clear:",
    ]

    for target in plan.targets:
        status = "optional" if target.optional else "canonical"
        existence = "exists" if target.path.exists() else "missing"
        lines.append(f"- [{status}] {target.path.relative_to(REPO_ROOT).as_posix()} ({target.kind}, {existence})")
        lines.append(f"  reason: {target.reason}")

    lines.extend(
        [
            "",
            "Preserved by default:",
        ]
    )
    for preserved in plan.preserved_paths:
        lines.append(f"- {preserved}")

    lines.extend(
        [
            "",
            "Notes:",
        ]
    )
    for note in plan.notes:
        lines.append(f"- {note}")

    return "\n".join(lines)


def execute_reset_plan(plan: ResetPlan) -> None:
    for target in plan.targets:
        if not target.path.exists():
            continue
        if target.kind == "file":
            target.path.unlink()
        else:
            shutil.rmtree(target.path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or execute a conservative research-state reset. "
            "Dry-run is the default."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("soft", "hard"),
        default="soft",
        help=(
            "soft: clear canonical DB + multiseed + Run Lab staging. "
            "hard: also clear manual analysis outputs."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the reset. Without this flag, the script only prints a dry-run plan.",
    )
    parser.add_argument(
        "--include-legacy-db",
        action="store_true",
        help="Also clear data/evolution.db if you explicitly want to remove the old legacy database file.",
    )
    parser.add_argument(
        "--include-legacy-artifacts",
        action="store_true",
        help="Also clear artifacts/runs and artifacts/batches after explicit operator review.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_reset_plan(
        mode=args.mode,
        include_legacy_db=bool(args.include_legacy_db),
        include_legacy_artifacts=bool(args.include_legacy_artifacts),
        destructive=bool(args.execute),
    )

    print(format_reset_plan(plan))

    if not args.execute:
        print("")
        print("No files were deleted. Re-run with --execute to perform the reset.")
        return 0

    execute_reset_plan(plan)
    print("")
    print("Research reset completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
