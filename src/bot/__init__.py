"""Discord bot package entry point."""

# 將 `main` 由子模組提升至封包層級，避免 Pylance `reportUnsupportedDunderAll`。
from .main import main  # noqa: F401

__all__ = ["main"]
