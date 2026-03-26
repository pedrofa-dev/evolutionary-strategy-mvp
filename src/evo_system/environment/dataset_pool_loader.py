from __future__ import annotations

import json
from pathlib import Path


class DatasetPoolLoader:
    def __init__(
        self,
        pool_config_path: Path = Path("configs/dataset_pool.json"),
    ) -> None:
        self.pool_config_path = pool_config_path

    def load_paths(
        self,
        dataset_root: Path,
        dataset_mode: str = "legacy",
        dataset_catalog_id: str | None = None,
    ) -> tuple[list[Path], list[Path]]:
        if dataset_mode == "manifest":
            return self._load_from_manifest_root(
                dataset_root=dataset_root,
                dataset_catalog_id=dataset_catalog_id,
            )

        if self.pool_config_path.exists():
            return self._load_from_pool_config(dataset_root)

        return self._load_all_available_paths(dataset_root)

    def _load_from_manifest_root(
        self,
        dataset_root: Path,
        dataset_catalog_id: str | None,
    ) -> tuple[list[Path], list[Path]]:
        if not dataset_catalog_id:
            raise ValueError("dataset_catalog_id is required for manifest dataset mode")

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

    def _load_from_pool_config(self, dataset_root: Path) -> tuple[list[Path], list[Path]]:
        data = json.loads(self.pool_config_path.read_text(encoding="utf-8"))

        train_entries = data.get("train", [])
        validation_entries = data.get("validation", [])

        train_paths = [dataset_root / Path(entry) for entry in train_entries]
        validation_paths = [dataset_root / Path(entry) for entry in validation_entries]

        missing_paths = [
            path for path in [*train_paths, *validation_paths] if not path.exists()
        ]
        if missing_paths:
            missing_str = "\n".join(str(path) for path in missing_paths)
            raise FileNotFoundError(
                f"Some dataset paths defined in {self.pool_config_path} do not exist:\n{missing_str}"
            )

        if not train_paths:
            raise ValueError("dataset_pool.json defines an empty train pool")

        if not validation_paths:
            raise ValueError("dataset_pool.json defines an empty validation pool")

        return train_paths, validation_paths

    def _load_all_available_paths(self, dataset_root: Path) -> tuple[list[Path], list[Path]]:
        train_root = dataset_root / "train"
        validation_root = dataset_root / "validation"

        train_paths = sorted(train_root.rglob("*.csv"))
        validation_paths = sorted(validation_root.rglob("*.csv"))

        if not train_paths:
            raise FileNotFoundError(f"No train datasets found under {train_root}")

        if not validation_paths:
            raise FileNotFoundError(f"No validation datasets found under {validation_root}")

        return train_paths, validation_paths
