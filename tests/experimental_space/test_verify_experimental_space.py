from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "verify_experimental_space.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "verify_experimental_space_script",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_experimental_space_summary_reports_expected_core_counts() -> None:
    module = _load_script_module()

    summary = module.build_verification_summary()

    assert summary["policy_engine_name"] == "policy_v2_default_engine"
    assert summary["runtime_decision_policy_name"] == "policy_v2_default"
    assert summary["policy_engine_count"] >= 1
    assert summary["gene_type_definition_count"] >= 4
    assert summary["signal_pack_count"] >= 2
    assert summary["experiment_preset_count"] >= 2
    assert summary["asset_counts"]["signal_packs"] >= 1
    assert summary["asset_counts"]["experiment_presets"] >= 1


def test_verify_experimental_space_main_prints_readable_summary(
    capsys,
) -> None:
    module = _load_script_module()

    exit_code = module.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Experimental space verification" in captured.out
    assert "Default policy compatibility" in captured.out
    assert "Catalog counts:" in captured.out
    assert "Asset counts:" in captured.out
