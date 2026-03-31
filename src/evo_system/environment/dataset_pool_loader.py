from pathlib import Path


class DatasetPoolLoader:
    def load_paths(
        self,
        dataset_root: Path,
        dataset_catalog_id: str,
    ) -> tuple[list[Path], list[Path]]:
        catalog_root = dataset_root / dataset_catalog_id
        train_root = catalog_root / "train"
        validation_root = catalog_root / "validation"

        train_paths = sorted(train_root.rglob("candles.csv"))
        validation_paths = sorted(validation_root.rglob("candles.csv"))

        if not train_paths:
            raise FileNotFoundError(f"No train datasets found under {train_root}")

        if not validation_paths:
            raise FileNotFoundError(f"No validation datasets found under {validation_root}")

        return train_paths, validation_paths
