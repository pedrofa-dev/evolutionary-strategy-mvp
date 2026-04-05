from evo_system.experimental_space.registry import NamedRegistry


def test_named_registry_register_get_list_and_has() -> None:
    registry: NamedRegistry[int] = NamedRegistry()

    registry.register("beta", 2)
    registry.register("alpha", 1, default=True)

    assert registry.get("alpha") == 1
    assert registry.get("beta") == 2
    assert registry.has("alpha") is True
    assert registry.has("missing") is False
    assert registry.list() == ["alpha", "beta"]
    assert registry.list_names() == ["alpha", "beta"]
    assert registry.default_name == "alpha"
    assert registry.get_default() == 1


def test_named_registry_raises_clear_error_for_unknown_item() -> None:
    registry: NamedRegistry[str] = NamedRegistry()
    registry.register("known", "value")

    try:
        registry.get("missing")
    except KeyError as exc:
        assert str(exc) == "'Unknown registry item: missing'"
    else:
        raise AssertionError("Expected NamedRegistry.get to raise KeyError.")
