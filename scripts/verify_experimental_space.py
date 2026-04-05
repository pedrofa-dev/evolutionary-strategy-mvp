from __future__ import annotations

import argparse
from typing import Any

from application.catalog import ExperimentalCatalogApplicationService
from evo_system.experimental_space import (
    get_default_decision_policy,
    get_default_policy_engine,
)
from evo_system.experimental_space.asset_loader import (
    ASSETS_ROOT,
    load_all_declarative_assets,
)


def build_verification_summary() -> dict[str, Any]:
    service = ExperimentalCatalogApplicationService(asset_root=ASSETS_ROOT)
    snapshot = service.get_catalog_snapshot()
    assets = load_all_declarative_assets(ASSETS_ROOT, validate_references=True)

    engine_policy = get_default_policy_engine().build_decision_policy()
    runtime_policy = get_default_decision_policy()
    if engine_policy.name != runtime_policy.name:
        raise RuntimeError(
            "Default policy engine is not compatible with the default runtime decision policy."
        )

    return {
        "policy_engine_name": get_default_policy_engine().name,
        "runtime_decision_policy_name": runtime_policy.name,
        "signal_plugin_count": len(snapshot.signal_plugins),
        "policy_engine_count": len(snapshot.policy_engines),
        "gene_type_definition_count": len(snapshot.gene_type_definitions),
        "signal_pack_count": len(snapshot.signal_packs),
        "genome_schema_count": len(snapshot.genome_schemas),
        "decision_policy_count": len(snapshot.decision_policies),
        "mutation_profile_count": len(snapshot.mutation_profiles),
        "experiment_preset_count": len(snapshot.experiment_presets),
        "asset_counts": {
            asset_type: len(asset_group) for asset_type, asset_group in assets.items()
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small verification pass over experimental-space metadata."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    summary = build_verification_summary()

    print("Experimental space verification")
    print(
        "Default policy compatibility: "
        f"{summary['policy_engine_name']} -> {summary['runtime_decision_policy_name']}"
    )
    print(
        "Catalog counts: "
        f"signal_plugins={summary['signal_plugin_count']} "
        f"policy_engines={summary['policy_engine_count']} "
        f"gene_type_definitions={summary['gene_type_definition_count']} "
        f"signal_packs={summary['signal_pack_count']} "
        f"genome_schemas={summary['genome_schema_count']} "
        f"decision_policies={summary['decision_policy_count']} "
        f"mutation_profiles={summary['mutation_profile_count']} "
        f"experiment_presets={summary['experiment_preset_count']}"
    )
    print(
        "Asset counts: "
        + " ".join(
            f"{asset_type}={count}"
            for asset_type, count in summary["asset_counts"].items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
