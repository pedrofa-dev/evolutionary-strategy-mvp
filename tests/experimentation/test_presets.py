from evo_system.experimentation.presets import (
    PRESET_STANDARD,
    deserialize_preset,
    serialize_preset,
)


def test_preset_serialization_roundtrip_is_stable() -> None:
    payload = serialize_preset(PRESET_STANDARD)

    assert payload == {
        "name": "standard",
        "generations": 25,
        "max_seeds": 6,
        "seeds": None,
    }
    assert deserialize_preset(payload) == PRESET_STANDARD


def test_preset_serialization_handles_none() -> None:
    assert serialize_preset(None) is None
    assert deserialize_preset(None) is None
