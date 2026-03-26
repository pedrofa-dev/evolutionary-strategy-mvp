from pathlib import Path

from evo_system.environment.dataset_pool_loader import DatasetPoolLoader


def test_dataset_pool_loader_supports_manifest_mode(tmp_path: Path) -> None:
    catalog_root = tmp_path / "core_1h_spot"
    train_dataset = catalog_root / "train" / "dataset_a"
    validation_dataset = catalog_root / "validation" / "dataset_b"

    train_dataset.mkdir(parents=True)
    validation_dataset.mkdir(parents=True)

    (train_dataset / "candles.csv").write_text("x", encoding="utf-8")
    (validation_dataset / "candles.csv").write_text("x", encoding="utf-8")

    loader = DatasetPoolLoader(pool_config_path=tmp_path / "missing_dataset_pool.json")
    train_paths, validation_paths = loader.load_paths(
        dataset_root=tmp_path,
        dataset_mode="manifest",
        dataset_catalog_id="core_1h_spot",
    )

    assert train_paths == [train_dataset / "candles.csv"]
    assert validation_paths == [validation_dataset / "candles.csv"]
