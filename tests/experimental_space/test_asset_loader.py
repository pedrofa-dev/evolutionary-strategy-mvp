from pathlib import Path

from evo_system.experimental_space.asset_loader import (
    ASSETS_ROOT,
    ASSET_DIRECTORY_NAMES,
    DeclarativeAsset,
    ensure_asset_directories,
    load_all_declarative_assets,
    load_declarative_asset,
    load_declarative_assets,
    load_plugin_module,
    validate_declarative_asset_references,
)


def test_load_declarative_assets_reads_valid_json_assets(tmp_path: Path) -> None:
    asset_dir = tmp_path / "signal_packs"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "spot.json").write_text(
        '{"id":"spot_pack","signals":[{"signal_id":"trend_strength_medium_v1"}]}',
        encoding="utf-8",
    )

    assets = load_declarative_assets(asset_dir, asset_type="signal_packs")

    assert len(assets) == 1
    assert isinstance(assets[0], DeclarativeAsset)
    assert assets[0].name == "spot_pack"
    assert assets[0].to_dict()["asset_type"] == "signal_packs"


def test_load_declarative_assets_raises_clear_error_for_invalid_asset(tmp_path: Path) -> None:
    asset_dir = tmp_path / "signal_packs"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "broken.json").write_text(
        '{"id":"broken_pack"}',
        encoding="utf-8",
    )

    try:
        load_declarative_assets(asset_dir, asset_type="signal_packs")
    except ValueError as exc:
        assert "'signals'" in str(exc)
    else:
        raise AssertionError("Expected invalid asset to raise ValueError.")


def test_plugin_loading_is_separate_from_asset_loading(tmp_path: Path, monkeypatch) -> None:
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "demo_plugin.py").write_text(
        "PLUGIN_NAME = 'demo'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(plugin_root))

    asset_root = tmp_path / "assets"
    directories = ensure_asset_directories(asset_root)
    (directories["signal_packs"] / "pack.json").write_text(
        '{"id":"pack_a","signals":[{"signal_id":"trend_strength_medium_v1"}]}',
        encoding="utf-8",
    )

    plugin = load_plugin_module("demo_plugin")
    assets = load_all_declarative_assets(asset_root)

    assert plugin.module_name == "demo_plugin"
    assert getattr(plugin.module, "PLUGIN_NAME") == "demo"
    assert list(assets) == list(ASSET_DIRECTORY_NAMES)
    assert assets["signal_packs"][0].name == "pack_a"
    assert assets["gene_catalogs"] == []


def test_load_all_declarative_assets_does_not_create_directories_on_read(
    tmp_path: Path,
) -> None:
    asset_root = tmp_path / "assets"

    assets = load_all_declarative_assets(asset_root)

    assert list(assets) == list(ASSET_DIRECTORY_NAMES)
    assert all(values == [] for values in assets.values())
    assert asset_root.exists() is False


def test_load_plugin_module_preserves_nested_import_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "nested_fail.py").write_text(
        "import missing_dependency_for_plugin\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(plugin_root))

    try:
        load_plugin_module("nested_fail")
    except ModuleNotFoundError as exc:
        assert exc.name == "missing_dependency_for_plugin"
    else:
        raise AssertionError("Expected nested plugin import failure to propagate.")


def test_load_declarative_asset_supports_id_as_canonical_identifier(
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "decision_policy.json"
    asset_path.write_text(
        (
            '{"id":"weighted_policy_v1","engine":"policy_v2_default_engine",'
            '"entry":{"trigger_gene":"entry_trigger","signals":['
            '{"signal":"trend","weight_gene_field":"trend_weight"}]},'
            '"exit":{"policy_gene":"exit_policy","trade_control_gene":"trade_control"}}'
        ),
        encoding="utf-8",
    )

    asset = load_declarative_asset(asset_path, asset_type="decision_policies")

    assert asset.name == "weighted_policy_v1"


def test_load_all_declarative_assets_can_validate_experiment_preset_references(
    tmp_path: Path,
) -> None:
    directories = ensure_asset_directories(tmp_path)
    (directories["signal_packs"] / "core.json").write_text(
        '{"id":"core_trend_v1","signals":[{"signal_id":"trend_strength_medium_v1"}]}',
        encoding="utf-8",
    )
    (directories["genome_schemas"] / "schema.json").write_text(
        (
            '{"id":"basic_entry_exit_v1","gene_catalog":"modular_genome_v1_gene_catalog",'
            '"modules":['
            '{"name":"entry_context","gene_type":"entry_context","required":true},'
            '{"name":"entry_trigger","gene_type":"entry_trigger","required":true},'
            '{"name":"exit_policy","gene_type":"exit_policy","required":true},'
            '{"name":"trade_control","gene_type":"trade_control","required":true}'
            ']}'
        ),
        encoding="utf-8",
    )
    (directories["decision_policies"] / "policy.json").write_text(
        (
            '{"id":"weighted_momentum_v1","engine":"policy_v2_default_engine",'
            '"entry":{"trigger_gene":"entry_trigger","signals":['
            '{"signal":"trend","weight_gene_field":"trend_weight"}]},'
            '"exit":{"policy_gene":"exit_policy","trade_control_gene":"trade_control"}}'
        ),
        encoding="utf-8",
    )
    (directories["mutation_profiles"] / "profile.json").write_text(
        (
            '{"id":"balanced_search_v1","profile":{'
            '"strong_mutation_probability":0.1,'
            '"numeric_delta_scale":1.0,'
            '"flag_flip_probability":0.05,'
            '"weight_delta":0.2,'
            '"window_step_mode":"default"}}'
        ),
        encoding="utf-8",
    )
    (directories["experiment_presets"] / "preset.json").write_text(
        (
            '{"id":"btc_1h_probe_v1","signal_pack":"core_trend_v1",'
            '"genome_schema":"basic_entry_exit_v1",'
            '"decision_policy":"weighted_momentum_v1",'
            '"mutation_profile":"balanced_search_v1",'
            '"dataset":{"asset":"BTC","timeframe":"1h"}}'
        ),
        encoding="utf-8",
    )

    assets = load_all_declarative_assets(tmp_path, validate_references=True)

    assert assets["experiment_presets"][0].name == "btc_1h_probe_v1"


def test_genome_schema_asset_raises_clear_error_for_unknown_gene_catalog(
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "schema.json"
    asset_path.write_text(
        (
            '{"id":"broken_schema","gene_catalog":"missing_catalog","modules":['
            '{"name":"entry_context","gene_type":"entry_context","required":true},'
            '{"name":"entry_trigger","gene_type":"entry_trigger","required":true},'
            '{"name":"exit_policy","gene_type":"exit_policy","required":true},'
            '{"name":"trade_control","gene_type":"trade_control","required":true}'
            ']}'
        ),
        encoding="utf-8",
    )

    try:
        load_declarative_asset(asset_path, asset_type="genome_schemas")
    except ValueError as exc:
        assert "missing_catalog" in str(exc)
        assert "gene_catalog" in str(exc)
    else:
        raise AssertionError("Expected unknown gene catalog to raise ValueError.")


def test_genome_schema_asset_raises_clear_error_for_unknown_gene_type(
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "schema.json"
    asset_path.write_text(
        (
            '{"id":"broken_schema","gene_catalog":"modular_genome_v1_gene_catalog",'
            '"modules":['
            '{"name":"entry_context","gene_type":"entry_context","required":true},'
            '{"name":"entry_trigger","gene_type":"missing_gene_type","required":true},'
            '{"name":"exit_policy","gene_type":"exit_policy","required":true},'
            '{"name":"trade_control","gene_type":"trade_control","required":true}'
            ']}'
        ),
        encoding="utf-8",
    )

    try:
        load_declarative_asset(asset_path, asset_type="genome_schemas")
    except ValueError as exc:
        assert "missing_gene_type" in str(exc)
        assert "gene_type" in str(exc)
    else:
        raise AssertionError("Expected unknown gene type to raise ValueError.")


def test_genome_schema_asset_raises_clear_error_for_incompatible_module_order(
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "schema.json"
    asset_path.write_text(
        (
            '{"id":"broken_schema","gene_catalog":"modular_genome_v1_gene_catalog",'
            '"modules":['
            '{"name":"entry_trigger","gene_type":"entry_trigger","required":true},'
            '{"name":"entry_context","gene_type":"entry_context","required":true},'
            '{"name":"exit_policy","gene_type":"exit_policy","required":true},'
            '{"name":"trade_control","gene_type":"trade_control","required":true}'
            ']}'
        ),
        encoding="utf-8",
    )

    try:
        load_declarative_asset(asset_path, asset_type="genome_schemas")
    except ValueError as exc:
        assert "runtime slot order" in str(exc)
    else:
        raise AssertionError("Expected incompatible module order to raise ValueError.")


def test_validate_declarative_asset_references_raises_clear_error_for_missing_reference(
    tmp_path: Path,
) -> None:
    directories = ensure_asset_directories(tmp_path)
    (directories["experiment_presets"] / "preset.json").write_text(
        (
            '{"id":"broken_probe_v1","signal_pack":"missing_signal_pack",'
            '"genome_schema":"missing_schema",'
            '"decision_policy":"missing_policy",'
            '"mutation_profile":"missing_profile",'
            '"dataset":{"asset":"BTC","timeframe":"1h"}}'
        ),
        encoding="utf-8",
    )

    assets = load_all_declarative_assets(tmp_path)

    try:
        validate_declarative_asset_references(assets)
    except ValueError as exc:
        assert "signal_pack" in str(exc)
        assert "missing_signal_pack" in str(exc)
    else:
        raise AssertionError("Expected missing asset reference to raise ValueError.")


def test_repo_example_assets_load_cleanly() -> None:
    assets = load_all_declarative_assets(ASSETS_ROOT, validate_references=True)

    assert assets["signal_packs"]
    assert assets["genome_schemas"]
    assert assets["decision_policies"]
    assert assets["mutation_profiles"]
    assert assets["experiment_presets"]
