from pathlib import Path

from evo_system.environment.csv_loader import load_historical_candles


def test_load_historical_candles_reads_csv_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "market.csv"
    csv_path.write_text(
        "1,100,105,99,104,1000,2,2000,10,500,1000,0\n"
        "2,104,108,103,107,1200,3,2200,12,600,1100,0\n",
        encoding="utf-8",
    )

    candles = load_historical_candles(str(csv_path))

    assert len(candles) == 2
    assert candles[0].timestamp == "1"
    assert candles[0].open == 100.0
    assert candles[0].high == 105.0
    assert candles[0].low == 99.0
    assert candles[0].close == 104.0
    assert candles[1].timestamp == "2"
    assert candles[1].close == 107.0