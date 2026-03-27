from pathlib import Path

import pytest

from evo_system.experimentation.champion_evaluation import (
    load_genome_from_json,
    resolve_dataset_paths,
)


def test_load_genome_from_json_supports_plain_genome_dict(tmp_path: Path) -> None:
    genome_path = tmp_path / "genome.json"
    genome_path.write_text(
        (
            "{"
            '"threshold_open": 0.8,'
            '"threshold_close": 0.4,'
            '"position_size": 0.2,'
            '"stop_loss": 0.05,'
            '"take_profit": 0.1'
            "}"
        ),
        encoding="utf-8",
    )

    genome = load_genome_from_json(genome_path)

    assert genome.threshold_open == 0.8
    assert genome.weight_trend_strength == 0.0
    assert genome.weight_realized_volatility == 0.0


def test_load_genome_from_json_supports_wrapped_genome_dict(tmp_path: Path) -> None:
    genome_path = tmp_path / "agent.json"
    genome_path.write_text(
        (
            "{"
            '"id": "agent-1",'
            '"genome": {'
            '"threshold_open": 0.8,'
            '"threshold_close": 0.4,'
            '"position_size": 0.2,'
            '"stop_loss": 0.05,'
            '"take_profit": 0.1,'
            '"weight_trend_strength": 0.2,'
            '"weight_realized_volatility": -0.1'
            "}"
            "}"
        ),
        encoding="utf-8",
    )

    genome = load_genome_from_json(genome_path)

    assert genome.weight_trend_strength == 0.2
    assert genome.weight_realized_volatility == -0.1


def test_resolve_dataset_paths_supports_manifest_external_layer(tmp_path: Path) -> None:
    dataset_path = (
        tmp_path
        / "core_1h_spot"
        / "external"
        / "BTCUSDT_1h_2022-11-01_2022-12-15"
        / "candles.csv"
    )
    dataset_path.parent.mkdir(parents=True)
    dataset_path.write_text("timestamp,open,high,low,close\n", encoding="utf-8")

    dataset_paths = resolve_dataset_paths(
        dataset_root=tmp_path,
        dataset_catalog_id="core_1h_spot",
        dataset_layer="external",
        direct_dataset_paths=None,
    )

    assert dataset_paths == [dataset_path]


def test_resolve_dataset_paths_rejects_missing_layer_for_catalog(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dataset_catalog_id and dataset_layer are required"):
        resolve_dataset_paths(
            dataset_root=tmp_path,
            dataset_catalog_id="core_1h_spot",
            dataset_layer=None,
            direct_dataset_paths=None,
        )
