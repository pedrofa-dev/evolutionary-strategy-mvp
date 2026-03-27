import csv

from evo_system.reporting.report_builder import export_flat_csv


def test_export_flat_csv_supports_rows_with_new_genome_weights(tmp_path) -> None:
    csv_path = tmp_path / "champions_flat.csv"
    rows = [
        {
            "id": 1,
            "config_name": "legacy",
            "weight_ret_short": 0.5,
        },
        {
            "id": 2,
            "config_name": "new",
            "weight_ret_short": 0.7,
            "weight_trend_strength": 0.2,
            "weight_realized_volatility": -0.1,
            "weight_trend_long": 0.3,
            "weight_breakout": -0.4,
        },
    ]

    export_flat_csv(rows, csv_path)

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        exported_rows = list(reader)

    assert "weight_trend_strength" in reader.fieldnames
    assert "weight_realized_volatility" in reader.fieldnames
    assert "weight_trend_long" in reader.fieldnames
    assert "weight_breakout" in reader.fieldnames
    assert exported_rows[0]["weight_trend_strength"] == ""
    assert exported_rows[0]["weight_realized_volatility"] == ""
    assert exported_rows[0]["weight_trend_long"] == ""
    assert exported_rows[0]["weight_breakout"] == ""
    assert exported_rows[1]["weight_trend_strength"] == "0.2"
    assert exported_rows[1]["weight_realized_volatility"] == "-0.1"
    assert exported_rows[1]["weight_trend_long"] == "0.3"
    assert exported_rows[1]["weight_breakout"] == "-0.4"
