from pathlib import Path

from evo_system.environment.dataset_pool_loader import DatasetPoolLoader


def test_load_paths_returns_train_and_validation_csvs(tmp_path: Path) -> None:
    train_spot = tmp_path / "train" / "spot"
    validation_spot = tmp_path / "validation" / "spot"

    train_spot.mkdir(parents=True)
    validation_spot.mkdir(parents=True)

    (train_spot / "BTCUSDT-1h-2025-10.csv").write_text("x", encoding="utf-8")
    (train_spot / "ETHUSDT-1h-2025-10.csv").write_text("x", encoding="utf-8")
    (validation_spot / "BTCUSDT-1h-2026-01.csv").write_text("x", encoding="utf-8")

    loader = DatasetPoolLoader()

    train_paths, validation_paths = loader.load_paths(tmp_path)

    assert len(train_paths) == 2
    assert len(validation_paths) == 1
    assert train_paths[0].suffix == ".csv"
    assert validation_paths[0].suffix == ".csv"