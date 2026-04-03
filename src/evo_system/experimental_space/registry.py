from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class NamedRegistry(Generic[T]):
    """Minimal registry used by phase-1 modularization defaults.

    The goal is to make future modular selection explicit without changing the
    effective runtime behavior in the current phase.
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

    def list_names(self) -> list[str]:
        return sorted(self._items)

    @property
    def default_name(self) -> str | None:
        return self._default_name
