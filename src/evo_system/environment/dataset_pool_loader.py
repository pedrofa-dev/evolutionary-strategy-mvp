from pathlib import Path


class DatasetPoolLoader:
    """
    Loads dataset file paths from train and validation pools.
    """

    def load_paths(self, root: str | Path) -> tuple[list[Path], list[Path]]:
        root_path = Path(root)

        train_paths = sorted((root_path / "train").rglob("*.csv"))
        validation_paths = sorted((root_path / "validation").rglob("*.csv"))

        if not train_paths:
            raise ValueError("No training datasets found")
        if not validation_paths:
            raise ValueError("No validation datasets found")

        return train_paths, validation_paths