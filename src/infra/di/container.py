"""Core dependency injection container implementation."""

from __future__ import annotations

import inspect
import threading
import types
from collections.abc import Callable
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

from src.infra.di.lifecycle import Lifecycle

T = TypeVar("T")


class DependencyContainer:
    """Dependency injection container with lifecycle management and type inference."""

    def __init__(self) -> None:
        """Initialize an empty container."""
        self._registrations: dict[type[Any], tuple[Callable[[], Any], Lifecycle]] = {}
        self._singletons: dict[type[Any], Any] = {}
        self._thread_locals: dict[int, dict[type[Any], Any]] = {}
        self._lock = threading.RLock()
        self._resolving: set[type[Any]] = set()

    def register(
        self,
        service_type: type[T],
        factory: Callable[[], T] | None = None,
        *,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
    ) -> None:
        """Register a service type with optional factory and lifecycle.

        Args:
            service_type: The type to register (used as the key).
            factory: Optional factory function. If None, the container will attempt
                to infer dependencies from the constructor.
            lifecycle: How instances are managed (default: SINGLETON).

        Raises:
            ValueError: If service_type is already registered.
        """
        if service_type in self._registrations:
            raise ValueError(f"Service {service_type.__name__} is already registered")

        if factory is None:
            factory = self._create_auto_factory(service_type)

        self._registrations[service_type] = (factory, lifecycle)

    def register_instance(self, service_type: type[T], instance: T) -> None:
        """Register a pre-created instance as a singleton.

        Args:
            service_type: The type to register.
            instance: The instance to use.

        Raises:
            ValueError: If service_type is already registered.
        """
        if service_type in self._registrations:
            raise ValueError(f"Service {service_type.__name__} is already registered")

        self._registrations[service_type] = (lambda: instance, Lifecycle.SINGLETON)
        self._singletons[service_type] = instance

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service instance based on its registered lifecycle.

        Args:
            service_type: The type to resolve.

        Returns:
            An instance of the requested type.

        Raises:
            KeyError: If the service is not registered.
            RuntimeError: If circular dependency is detected.
        """
        if service_type not in self._registrations:
            raise KeyError(f"Service {service_type.__name__} is not registered")

        # Detect circular dependencies
        if service_type in self._resolving:
            cycle = (
                " -> ".join(t.__name__ for t in self._resolving) + f" -> {service_type.__name__}"
            )
            raise RuntimeError(f"Circular dependency detected: {cycle}")

        factory, lifecycle = self._registrations[service_type]

        try:
            self._resolving.add(service_type)

            if lifecycle == Lifecycle.SINGLETON:
                return self._resolve_singleton(service_type, factory)
            elif lifecycle == Lifecycle.FACTORY:
                return self._resolve_factory(service_type, factory)
            elif lifecycle == Lifecycle.THREAD_LOCAL:
                return self._resolve_thread_local(service_type, factory)
            else:
                raise ValueError(f"Unknown lifecycle: {lifecycle}")

        finally:
            self._resolving.discard(service_type)

    def _resolve_singleton(self, service_type: type[T], factory: Callable[[], T]) -> T:
        """Resolve or create a singleton instance."""
        if service_type in self._singletons:
            return cast(T, self._singletons[service_type])

        with self._lock:
            # Double-check after acquiring lock
            if service_type in self._singletons:
                return cast(T, self._singletons[service_type])

            instance = factory()
            self._singletons[service_type] = instance
            return instance

    def _resolve_factory(self, service_type: type[T], factory: Callable[[], T]) -> T:
        """Resolve a new instance using factory lifecycle."""
        return factory()

    def _resolve_thread_local(self, service_type: type[T], factory: Callable[[], T]) -> T:
        """Resolve a thread-local instance."""
        thread_id = threading.get_ident()
        if thread_id not in self._thread_locals:
            self._thread_locals[thread_id] = {}

        if service_type not in self._thread_locals[thread_id]:
            self._thread_locals[thread_id][service_type] = factory()

        return cast(T, self._thread_locals[thread_id][service_type])

    def _create_auto_factory(self, service_type: type[T]) -> Callable[[], T]:
        """Create a factory function that infers dependencies from constructor."""

        def factory() -> T:
            # Get constructor signature
            sig = inspect.signature(service_type.__init__)
            type_hints = get_type_hints(service_type.__init__)

            # Build arguments for constructor
            kwargs: dict[str, Any] = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get type hint
                param_type = type_hints.get(param_name)

                # If no type hint or type is Any, skip (assume optional or not injectable)
                if param_type is None or param_type is Any:
                    # If parameter has a default, skip it
                    if param.default != inspect.Parameter.empty:
                        continue
                    # Otherwise, we can't infer - skip for now
                    continue

                injectable_type = self._infer_injectable_type(param_type)
                if injectable_type is None:
                    if param.default != inspect.Parameter.empty:
                        continue
                    # Can't handle this annotation automatically
                    continue

                # Try to resolve the dependency
                try:
                    kwargs[param_name] = self.resolve(injectable_type)
                except KeyError:
                    # If not registered and has default, skip
                    if param.default != inspect.Parameter.empty:
                        continue
                    # Otherwise, re-raise
                    raise

            # Instantiate with resolved dependencies
            return service_type(**kwargs)

        return factory

    def is_registered(self, service_type: type[Any]) -> bool:
        """Check if a service type is registered.

        Args:
            service_type: The type to check.

        Returns:
            True if registered, False otherwise.
        """
        return service_type in self._registrations

    def clear(self) -> None:
        """Clear all registrations and cached instances.

        Useful for testing or resetting the container state.
        """
        with self._lock:
            self._registrations.clear()
            self._singletons.clear()
            self._thread_locals.clear()
            self._resolving.clear()

    def _infer_injectable_type(self, annotation: Any) -> type[Any] | None:
        """Normalize supported annotations (plain types or Optional[T]) to a type."""

        if isinstance(annotation, type):
            return annotation

        origin = get_origin(annotation)
        union_args: tuple[Any, ...] | None = None

        if origin in (types.UnionType, Union):
            union_args = get_args(annotation)
        elif isinstance(annotation, types.UnionType):
            union_args = getattr(annotation, "__args__", ())

        if union_args:
            non_none = [arg for arg in union_args if arg is not type(None)]
            has_none = len(non_none) < len(union_args)
            if has_none and len(non_none) == 1:
                candidate = non_none[0]
                if isinstance(candidate, type):
                    return candidate
            return None

        return None
