from pathlib import Path

from evo_system.environment.dataset_pool_loader import DatasetPoolLoader


def test_load_paths_returns_train_and_validation_csvs(tmp_path: Path) -> None:
    catalog_root = tmp_path / "core_1h_spot"
    train_spot = catalog_root / "train"
    validation_spot = catalog_root / "validation"

    train_spot.mkdir(parents=True)
    validation_spot.mkdir(parents=True)

    train_a = train_spot / "BTCUSDT_1h_train_a"
    train_b = train_spot / "ETHUSDT_1h_train_b"
    validation_a = validation_spot / "BTCUSDT_1h_validation_a"
    train_a.mkdir(parents=True)
    train_b.mkdir(parents=True)
    validation_a.mkdir(parents=True)

    (train_a / "candles.csv").write_text("x", encoding="utf-8")
    (train_b / "candles.csv").write_text("x", encoding="utf-8")
    (validation_a / "candles.csv").write_text("x", encoding="utf-8")

    loader = DatasetPoolLoader()

    train_paths, validation_paths = loader.load_paths(
        dataset_root=tmp_path,
        dataset_catalog_id="core_1h_spot",
    )

    assert len(train_paths) == 2
    assert len(validation_paths) == 1
    assert train_paths[0].suffix == ".csv"
    assert validation_paths[0].suffix == ".csv"
