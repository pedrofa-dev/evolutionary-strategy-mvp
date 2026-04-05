from pathlib import Path

from application.catalog import ExperimentalCatalogApplicationService
from evo_system.experimental_space.asset_loader import ensure_asset_directories


def test_application_catalog_service_exposes_serializable_catalog_payload() -> None:
    service = ExperimentalCatalogApplicationService()

    payload = service.get_catalog_payload()

    assert list(payload) == [
        "signal_plugins",
        "policy_engines",
        "gene_type_definitions",
        "signal_packs",
        "genome_schemas",
        "decision_policies",
        "mutation_profiles",
        "experiment_presets",
    ]
    assert payload["signal_plugins"] == []
    assert payload["policy_engines"][0]["category"] == "policy_engines"
    assert any(item["id"] == "btc_1h_probe_v1" for item in payload["experiment_presets"])


def test_application_catalog_service_preserves_runtime_and_asset_origins() -> None:
    service = ExperimentalCatalogApplicationService()

    snapshot = service.get_catalog_snapshot()

    assert any(item.origin == "runtime" for item in snapshot.signal_packs)
    assert any(item.origin == "asset" for item in snapshot.signal_packs)
    assert any(item.id == "policy_v2_default" for item in snapshot.decision_policies)
    assert any(item.id == "default_runtime_profile" for item in snapshot.mutation_profiles)


def test_application_catalog_service_handles_empty_asset_root_conservatively(
    tmp_path: Path,
) -> None:
    ensure_asset_directories(tmp_path)
    service = ExperimentalCatalogApplicationService(asset_root=tmp_path)

    payload = service.get_catalog_payload()

    assert payload["signal_plugins"] == []
    assert all(item["origin"] == "runtime" for item in payload["signal_packs"])
    assert all(item["origin"] == "runtime" for item in payload["genome_schemas"])
    assert all(item["origin"] == "runtime" for item in payload["experiment_presets"])
