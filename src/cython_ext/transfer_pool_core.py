from __future__ import annotations

from collections import defaultdict
from typing import Mapping

__all__ = ["TransferCheckStateStore"]


class TransferCheckStateStore:
    """Python fallback for the Cython state tracker."""

    __slots__ = ("_states", "_required")

    def __init__(self) -> None:
        self._states: dict[object, dict[str, int]] = defaultdict(dict)
        self._required = frozenset({"balance", "cooldown", "daily_limit"})

    def record(self, transfer_id: object, check_type: str, result: int) -> bool:
        state = self._states[transfer_id]
        state[check_type] = result
        return self._required.issubset(state.keys())

    def get_state(self, transfer_id: object) -> Mapping[str, int]:
        return self._states.get(transfer_id, {})

    def all_passed(self, transfer_id: object) -> bool:
        state = self._states.get(transfer_id)
        if not state:
            return False
        return all(state.get(name) == 1 for name in self._required)

    def snapshot(self) -> Mapping[object, Mapping[str, int]]:
        """Return a shallow copy of all states for inspection/testing."""
        return {k: dict(v) for k, v in self._states.items()}

    def remove(self, transfer_id: object) -> bool:
        return self._states.pop(transfer_id, None) is not None

    def clear(self) -> None:
        self._states.clear()
