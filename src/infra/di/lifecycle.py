"""Lifecycle management for dependency injection."""

from enum import Enum


class Lifecycle(Enum):
    """Lifecycle strategies for dependency resolution."""

    SINGLETON = "singleton"
    """Single instance shared across all resolutions."""

    FACTORY = "factory"
    """New instance created on each resolution."""

    THREAD_LOCAL = "thread_local"
    """One instance per thread (not commonly used in async contexts)."""
