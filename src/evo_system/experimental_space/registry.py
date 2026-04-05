from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class NamedRegistry(Generic[T]):
    """Minimal typed registry for modular experimental-space components.

    Why it exists:
    - The core already selects schemas, policies, signal packs, and presets by
      name.
    - A shared registry keeps that selection explicit and prepares the codebase
      for future plugin-style registration without changing runtime semantics.

    Compatibility:
    - ``list()`` returns registered names in sorted order.
    - ``list_names()`` is kept as an explicit alias for existing callers and
      for code that wants the intent spelled out.
    - ``has()`` provides a non-throwing existence check for future loading
      paths.
    """

    _items: dict[str, T] = field(default_factory=dict)
    _default_name: str | None = None

    def register(self, name: str, item: T, *, default: bool = False) -> T:
        self._items[name] = item

        if default or self._default_name is None:
            self._default_name = name

        return item

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"Unknown registry item: {name}") from exc

    def get_default(self) -> T:
        if self._default_name is None:
            raise LookupError("Registry has no default item")

        return self._items[self._default_name]

    def list(self) -> list[str]:
        """Return registered names in sorted order."""
        return sorted(self._items)

    def list_names(self) -> list[str]:
        """Explicit alias for ``list()`` kept for compatibility/readability."""
        return self.list()

    def has(self, name: str) -> bool:
        return name in self._items

    @property
    def default_name(self) -> str | None:
        return self._default_name
