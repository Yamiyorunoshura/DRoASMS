from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CurrencyConfig"]


@dataclass(slots=True, frozen=True)
class CurrencyConfig:
    guild_id: int
    currency_name: str
    currency_icon: str
