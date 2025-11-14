from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CurrencyConfigResult"]


@dataclass(slots=True, frozen=True)
class CurrencyConfigResult:
    """Python 後備版本，Cython 編譯後會以 cdef class 覆蓋。"""

    currency_name: str
    currency_icon: str
