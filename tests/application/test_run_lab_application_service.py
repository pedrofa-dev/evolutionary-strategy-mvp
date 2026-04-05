from __future__ import annotations

import json
from pathlib import Path

from application.run_lab import RunLabApplicationService


def _write_manifest(path: Path, *, catalog_id: str = "core_1h_spot") -> None:
    path.write_text(
        "\n".join(
            [
                f"catalog_id: {catalog_id}",
                "description: Core test catalog.",
                "market_type: spot",
                "timeframe: 1h",
                "datasets:",
                "  - id: BTCUSDT_1h_train",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2023-01-01",
                "    end: 2023-02-01",
                "    layer: train",
                "    regime_primary: trend",
                "    regime_secondary: breakout",
                "    volatility: medium",
                "    event_tag: test_train",
                "    notes: Train window.",
                "  - id: BTCUSDT_1h_validation",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2023-03-01",
                "    end: 2023-03-15",
                "    layer: validation",
                "    regime_primary: range",
                "    regime_secondary: mean_reversion",
                "    volatility: low",
                "    event_tag: test_validation",
                "    notes: Validation window.",
            ]
        ),
        encoding="utf-8",
    )


def _write_template(path: Path) -> None:
    payload = {
        "seed_start": 100,
        "seed_count": 6,
        "population_size": 18,
        "target_population_size": 18,
        "survivors_count": 4,
        "generations_planned": 25,
        "mutation_seed": 42,
        "trade_cost_rate": 0.0005,
        "cost_penalty_weight": 0.0,
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "decision_policy_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "mutation_profile": {
            "strong_mutation_probability": 0.055,
            "numeric_delta_scale": 0.75,
            "flag_flip_probability": 0.025,
            "weight_delta": 0.145,
            "window_step_mode": "default",
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_run_lab_bootstrap_exposes_canonical_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    bootstrap = service.get_bootstrap()

    assert bootstrap.defaults["template_config_name"] == "balanced_baseline.json"
    assert bootstrap.defaults["dataset_catalog_id"] == "core_1h_spot"
    assert bootstrap.defaults["signal_pack_name"] == "policy_v21_default"
    assert bootstrap.defaults["genome_schema_name"] == "policy_v2_default"
    assert bootstrap.defaults["decision_policy_name"] == "policy_v2_default"
    assert bootstrap.defaults["mutation_profile_name"] == "default_runtime_profile"
    assert bootstrap.defaults["experiment_preset_name"] == "standard"
    assert bootstrap.dataset_catalogs[0].split_summary == {"train": 1, "validation": 1}
    assert any(option.id == "policy_v2_default" for option in bootstrap.decision_policies)


def test_run_lab_save_run_config_writes_canonical_json(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    result = service.save_run_config(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "bnb run lab probe",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
        }
    )

    saved_path = repo_root / result.config_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert result.config_name == "bnb run lab probe.json"
    assert saved_payload["dataset_catalog_id"] == "core_1h_spot"
    assert saved_payload["seed_start"] == 111
    assert saved_payload["seed_count"] == 8
    assert any(
        "Current executable mutation profile" in warning
        for warning in result.warnings
    )


def test_run_lab_save_and_execute_launches_canonical_script_in_isolated_dir(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    captured: dict[str, object] = {}

    class DummyProcess:
        pid = 12345

    def fake_launcher(command, cwd, stdout, stderr):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["stderr"] = stderr
        return DummyProcess()

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        launcher=fake_launcher,
    )

    result = service.save_and_execute(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "bnb run lab execute",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
            "experiment_preset_name": "standard",
        }
    )

    assert result.pid == 12345
    assert captured["cwd"] == str(repo_root)
    assert "scripts/run_experiment.py" in captured["command"]
    assert "--preset" in captured["command"]
    assert result.launch_log_path.endswith("launch.log")
    assert (repo_root / result.saved_config.config_path).exists()
