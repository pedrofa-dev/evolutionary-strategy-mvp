import pytest

from evo_system.domain.genome import Genome


def test_genome_to_dict_returns_serializable_data() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    result = genome.to_dict()

    assert result == {
        "threshold_open": 0.8,
        "threshold_close": 0.4,
        "position_size": 0.2,
        "stop_loss": 0.05,
        "take_profit": 0.1,
    }


def test_genome_from_dict_builds_valid_genome() -> None:
    data = {
        "threshold_open": 0.8,
        "threshold_close": 0.4,
        "position_size": 0.2,
        "stop_loss": 0.05,
        "take_profit": 0.1,
    }

    genome = Genome.from_dict(data)

    assert genome.threshold_open == 0.8
    assert genome.threshold_close == 0.4
    assert genome.position_size == 0.2
    assert genome.stop_loss == 0.05
    assert genome.take_profit == 0.1


def test_genome_validation_fails_when_close_threshold_is_greater_than_open() -> None:
    with pytest.raises(ValueError, match="threshold_close must be less than or equal to threshold_open"):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.8,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
            }
        )


def test_genome_copy_with_returns_new_valid_genome() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    updated = genome.copy_with(position_size=0.3)

    assert updated.position_size == 0.3
    assert genome.position_size == 0.2