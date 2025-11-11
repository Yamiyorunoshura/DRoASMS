"""Service layer abstractions for Discord bot features.

將常用子模組提升到套件層級，
以符合 `__all__` 並通過型別檢查器的名稱存在性檢查。
"""

# 將子模組匯入為屬性，確保於套件命名空間可見
from . import adjustment_service as adjustment_service  # noqa: F401
from . import balance_service as balance_service  # noqa: F401
from . import transfer_service as transfer_service  # noqa: F401

__all__ = ["transfer_service", "balance_service", "adjustment_service"]
