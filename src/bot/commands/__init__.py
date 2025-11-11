"""Slash command modules for the Discord economy bot."""

# 匯入子模組以在封包層級導出，解決 Pylance `reportUnsupportedDunderAll`。
from . import balance as balance  # noqa: F401
from . import transfer as transfer  # noqa: F401

__all__ = ["transfer", "balance"]
