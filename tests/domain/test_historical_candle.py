from evo_system.domain.historical_candle import HistoricalCandle


def test_historical_candle_stores_ohlc_values() -> None:
    candle = HistoricalCandle(
        timestamp="1",
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
    )

    assert candle.timestamp == "1"
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 99.0
    assert candle.close == 104.0