from pathlib import Path

from evo_system.experimental_space.asset_loader import ensure_asset_directories
from evo_system.experimental_space.catalog_service import CatalogService


def test_catalog_service_lists_policy_engines_and_assets_from_repo() -> None:
    service = CatalogService()

    policy_engines = service.list_policy_engines()
    signal_packs = service.list_signal_packs()
    experiment_presets = service.list_experiment_presets()

    assert [entry.id for entry in policy_engines] == ["policy_v2_default_engine"]
    assert policy_engines[0].payload == {
        "name": "policy_v2_default_engine",
        "builds_decision_policy": "policy_v2_default",
    }
    assert any(entry.origin == "asset" and entry.id == "core_policy_v21_signals_v1" for entry in signal_packs)
    assert any(entry.origin == "runtime" and entry.id == "quick" for entry in experiment_presets)
    assert any(entry.origin == "asset" and entry.id == "btc_1h_probe_v1" for entry in experiment_presets)


def test_catalog_service_snapshot_is_serializable_and_stable() -> None:
    service = CatalogService()

    snapshot = service.get_catalog_snapshot().to_dict()

    assert list(snapshot) == [
        "signal_plugins",
        "policy_engines",
        "gene_type_definitions",
        "signal_packs",
        "genome_schemas",
        "decision_policies",
        "mutation_profiles",
        "experiment_presets",
    ]
    assert snapshot["signal_plugins"] == []
    assert snapshot["policy_engines"][0]["origin"] == "plugin"
    assert snapshot["gene_type_definitions"][0]["type"] == "gene_type_definition"
    assert snapshot["signal_packs"][0]["id"] <= snapshot["signal_packs"][-1]["id"]
    assert snapshot["signal_packs"][0]["file_path"] is None or ":" not in snapshot["signal_packs"][0]["file_path"]


def test_catalog_service_handles_empty_asset_root_reasonably(tmp_path: Path) -> None:
    ensure_asset_directories(tmp_path)
    service = CatalogService(asset_root=tmp_path)

    assert service.list_signal_plugins() == []
    assert all(entry.origin == "runtime" for entry in service.list_signal_packs())
    assert all(entry.origin == "runtime" for entry in service.list_genome_schemas())
    assert all(entry.origin == "runtime" for entry in service.list_experiment_presets())


def test_catalog_service_exposes_gene_type_definitions_with_catalog_metadata() -> None:
    service = CatalogService()

    definitions = service.list_gene_type_definitions()

    assert definitions
    assert definitions[0].origin == "runtime"
    assert definitions[0].payload is not None
    assert definitions[0].payload["gene_catalog_name"] == "modular_genome_v1_gene_catalog"
    assert definitions[0].payload["field_specs"]


def test_catalog_service_lists_expected_runtime_decision_policy_and_mutation_profile() -> None:
    service = CatalogService()

    decision_policies = service.list_decision_policies()
    mutation_profiles = service.list_mutation_profiles()

    assert any(
        entry.origin == "runtime" and entry.id == "policy_v2_default"
        for entry in decision_policies
    )
    assert any(
        entry.origin == "runtime" and entry.id == "default_runtime_profile"
        for entry in mutation_profiles
    )


def test_catalog_service_exposes_descriptions_for_example_assets() -> None:
    service = CatalogService()

    decision_policies = {entry.id: entry for entry in service.list_decision_policies()}
    signal_packs = {entry.id: entry for entry in service.list_signal_packs()}
    presets = {entry.id: entry for entry in service.list_experiment_presets()}

    assert decision_policies["weighted_policy_v2_v1"].description is not None
    assert signal_packs["core_policy_v21_signals_v1"].description is not None
    assert presets["btc_1h_probe_v1"].description is not None


def test_catalog_service_exposes_runtime_preset_descriptions_for_ui_clarity() -> None:
    service = CatalogService()

    presets = {entry.id: entry for entry in service.list_experiment_presets()}

    assert presets["quick"].description == "Runtime multiseed preset for very fast local iteration."
    assert presets["full"].description == "Runtime multiseed preset for the heaviest built-in evaluation budget."
