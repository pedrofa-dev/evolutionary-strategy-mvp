import csv
from pathlib import Path


RAW_ROOT = Path("data/raw")
NORMALIZED_ROOT = Path("data/real")


def looks_like_header(row: list[str]) -> bool:
    if not row:
        return False

    lowered = [cell.strip().lower() for cell in row]

    return (
        "open" in lowered
        or "high" in lowered
        or "low" in lowered
        or "close" in lowered
        or "open_time" in lowered
        or "timestamp" in lowered
    )


def normalize_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with open(source_path, newline="", encoding="utf-8") as source_file:
        reader = csv.reader(source_file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Empty CSV file: {source_path}")

    start_index = 1 if looks_like_header(rows[0]) else 0

    normalized_rows: list[list[str]] = [["timestamp", "open", "high", "low", "close"]]

    for row in rows[start_index:]:
        if not row:
            continue

        normalized_rows.append([
            str(row[0]).strip(),
            str(row[1]).strip(),
            str(row[2]).strip(),
            str(row[3]).strip(),
            str(row[4]).strip(),
        ])

    with open(destination_path, "w", newline="", encoding="utf-8") as destination_file:
        writer = csv.writer(destination_file)
        writer.writerows(normalized_rows)


def main() -> None:
    csv_paths = sorted(RAW_ROOT.rglob("*.csv"))

    if not csv_paths:
        raise ValueError("No CSV files found under data/raw")

    for source_path in csv_paths:
        relative_path = source_path.relative_to(RAW_ROOT)
        destination_path = NORMALIZED_ROOT / relative_path

        normalize_file(source_path, destination_path)
        print(f"Normalized: {source_path} -> {destination_path}")


if __name__ == "__main__":
    main()