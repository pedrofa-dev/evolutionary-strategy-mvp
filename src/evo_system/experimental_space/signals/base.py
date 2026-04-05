from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from evo_system.experimental_space.base import SignalPack


@runtime_checkable
class SignalPlugin(Protocol):
    """Future plugin contract for contributed signal packs.

    Scope of this phase:
    - This is only a plugin-system foundation seam.
    - The active runtime still resolves the built-in ``SignalPack`` instances
      through the existing defaults module and registries.

    Future intent:
    - A plugin should be able to expose one or more signal-pack definitions
      without forcing the core to import product/UI code.
    """

    name: str

    def build_signal_pack(self) -> "SignalPack":
        """Return the signal-pack implementation contributed by the plugin."""
