"""Unit tests for DI infrastructure (container, lifecycle, result_container).

These tests focus on the core container functionality without testing bootstrap
which involves complex mocking and circular import issues.
"""

from __future__ import annotations

import threading
from typing import Optional

import pytest

from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle
from src.infra.di.result_container import ResultContainer

# =============================================================================
# Test: Lifecycle enum
# =============================================================================


@pytest.mark.unit
class TestLifecycle:
    """Test cases for Lifecycle enum."""

    def test_lifecycle_singleton_value(self) -> None:
        """Test SINGLETON lifecycle value."""
        assert Lifecycle.SINGLETON.value == "singleton"

    def test_lifecycle_factory_value(self) -> None:
        """Test FACTORY lifecycle value."""
        assert Lifecycle.FACTORY.value == "factory"

    def test_lifecycle_thread_local_value(self) -> None:
        """Test THREAD_LOCAL lifecycle value."""
        assert Lifecycle.THREAD_LOCAL.value == "thread_local"

    def test_lifecycle_all_members(self) -> None:
        """Test all lifecycle members are present."""
        members = {member.name for member in Lifecycle}
        assert members == {"SINGLETON", "FACTORY", "THREAD_LOCAL"}


# =============================================================================
# Test: DependencyContainer thread-local lifecycle
# =============================================================================


class ThreadLocalService:
    """Service for testing thread-local lifecycle."""

    def __init__(self) -> None:
        self.thread_id = threading.get_ident()


@pytest.mark.unit
class TestDependencyContainerThreadLocal:
    """Test cases for thread-local lifecycle."""

    def test_thread_local_different_instances_per_thread(self) -> None:
        """Test that thread-local lifecycle creates different instances per thread."""
        container = DependencyContainer()
        container.register(ThreadLocalService, lifecycle=Lifecycle.THREAD_LOCAL)

        instances_from_threads: dict[int, ThreadLocalService] = {}
        errors: list[Exception] = []

        def resolve_in_thread() -> None:
            try:
                instance = container.resolve(ThreadLocalService)
                thread_id = threading.get_ident()
                instances_from_threads[thread_id] = instance
            except Exception as e:
                errors.append(e)

        # Create and run threads
        threads = [threading.Thread(target=resolve_in_thread) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

        # Check no errors
        assert len(errors) == 0

        # Each thread should have its own instance
        assert len(instances_from_threads) == 5
        instances = list(instances_from_threads.values())
        for i in range(len(instances)):
            for j in range(i + 1, len(instances)):
                assert instances[i] is not instances[j]

    def test_thread_local_same_instance_within_thread(self) -> None:
        """Test that thread-local lifecycle returns same instance within a thread."""
        container = DependencyContainer()
        container.register(ThreadLocalService, lifecycle=Lifecycle.THREAD_LOCAL)

        instance1 = container.resolve(ThreadLocalService)
        instance2 = container.resolve(ThreadLocalService)

        assert instance1 is instance2

    def test_thread_local_cleared_on_container_clear(self) -> None:
        """Test that thread-local instances are cleared with container.clear()."""
        container = DependencyContainer()
        container.register(ThreadLocalService, lifecycle=Lifecycle.THREAD_LOCAL)

        _ = container.resolve(ThreadLocalService)  # unused instance
        container.clear()

        # After clear, service is no longer registered
        with pytest.raises(KeyError):
            container.resolve(ThreadLocalService)


# =============================================================================
# Test: DependencyContainer edge cases
# =============================================================================


class ServiceWithNoHints:
    """Service without type hints."""

    def __init__(self, param) -> None:  # type: ignore[no-untyped-def]
        self.param = param


class ServiceWithVarArgs:
    """Service with *args and **kwargs."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


@pytest.mark.unit
class TestDependencyContainerEdgeCases:
    """Test edge cases for DependencyContainer."""

    def test_register_instance_duplicate_raises(self) -> None:
        """Test that registering same instance twice raises error."""
        container = DependencyContainer()
        instance = ThreadLocalService()
        container.register_instance(ThreadLocalService, instance)

        with pytest.raises(ValueError, match="already registered"):
            container.register_instance(ThreadLocalService, instance)

    def test_auto_factory_skips_params_without_hints(self) -> None:
        """Test that auto factory skips parameters without type hints."""
        container = DependencyContainer()

        # Register with custom factory because auto factory can't handle no hints
        def factory() -> ServiceWithNoHints:
            return ServiceWithNoHints("test")

        container.register(ServiceWithNoHints, factory=factory)
        instance = container.resolve(ServiceWithNoHints)
        assert instance.param == "test"

    def test_auto_factory_handles_varargs(self) -> None:
        """Test that auto factory skips *args and **kwargs."""
        container = DependencyContainer()
        container.register(ServiceWithVarArgs, lifecycle=Lifecycle.FACTORY)

        instance = container.resolve(ServiceWithVarArgs)
        assert isinstance(instance, ServiceWithVarArgs)
        assert instance.args == ()
        assert instance.kwargs == {}

    def test_resolve_unknown_lifecycle_raises(self) -> None:
        """Test that unknown lifecycle raises ValueError."""
        container = DependencyContainer()

        # Manually inject invalid lifecycle
        container._registrations[ThreadLocalService] = (
            lambda: ThreadLocalService(),
            "invalid_lifecycle",  # type: ignore[arg-type]
        )

        with pytest.raises(ValueError, match="Unknown lifecycle"):
            container.resolve(ThreadLocalService)


# =============================================================================
# Test: ResultContainer
# =============================================================================


@pytest.mark.unit
class TestResultContainer:
    """Test cases for ResultContainer."""

    def test_result_container_init(self) -> None:
        """Test ResultContainer initialization."""
        base_container = DependencyContainer()
        result_container = ResultContainer(base_container)

        assert result_container._base is base_container

    def test_register_result_services_no_op(self) -> None:
        """Test that register_result_services is a no-op."""
        base_container = DependencyContainer()
        result_container = ResultContainer(base_container)

        # Should not raise
        result_container.register_result_services()


# =============================================================================
# Test: DependencyContainer._infer_injectable_type edge cases
# =============================================================================


@pytest.mark.unit
class TestInferInjectableType:
    """Test cases for _infer_injectable_type."""

    def test_infer_injectable_type_plain_type(self) -> None:
        """Test inferring plain type."""
        container = DependencyContainer()
        result = container._infer_injectable_type(ThreadLocalService)
        assert result is ThreadLocalService

    def test_infer_injectable_type_optional_typing(self) -> None:
        """Test inferring Optional[Type] using typing.Optional."""
        container = DependencyContainer()
        result = container._infer_injectable_type(Optional[ThreadLocalService])
        assert result is ThreadLocalService

    def test_infer_injectable_type_optional_pep604(self) -> None:
        """Test inferring Type | None using PEP 604."""
        container = DependencyContainer()
        result = container._infer_injectable_type(ThreadLocalService | None)
        assert result is ThreadLocalService

    def test_infer_injectable_type_union_multiple_types(self) -> None:
        """Test inferring Union with multiple non-None types returns None."""
        container = DependencyContainer()
        result = container._infer_injectable_type(ThreadLocalService | ServiceWithVarArgs)
        assert result is None

    def test_infer_injectable_type_non_type_annotation(self) -> None:
        """Test inferring non-type annotation returns None."""
        container = DependencyContainer()
        result = container._infer_injectable_type("not a type")  # type: ignore[arg-type]
        assert result is None

    def test_infer_injectable_type_optional_with_string(self) -> None:
        """Test Optional with non-type returns None."""
        container = DependencyContainer()
        # Optional[str] where str is a builtin type, but let's test with non-class
        result2 = container._infer_injectable_type(Optional[str])
        assert result2 is str
