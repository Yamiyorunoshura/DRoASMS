"""Unit tests for dependency injection container."""

from __future__ import annotations

import threading
from typing import Optional
from unittest.mock import Mock

import pytest

from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle


class SimpleService:
    """Simple service for testing."""

    def __init__(self) -> None:
        self.value = "simple"


class ServiceWithDependency:
    """Service that depends on SimpleService."""

    def __init__(self, simple_service: SimpleService) -> None:
        self.simple_service = simple_service


class ServiceWithOptionalDependency:
    """Service with optional dependency."""

    def __init__(self, simple_service: Optional[SimpleService] = None) -> None:
        self.simple_service = simple_service


class ServiceWithPep604OptionalDependency:
    """Service using the ``SimpleService | None`` syntax for optional dependency."""

    def __init__(self, simple_service: SimpleService | None = None) -> None:
        self.simple_service = simple_service


class ServiceWithMultipleDependencies:
    """Service with multiple dependencies."""

    def __init__(
        self, simple_service: SimpleService, service_with_dep: ServiceWithDependency
    ) -> None:
        self.simple_service = simple_service
        self.service_with_dep = service_with_dep


class CircularServiceA:
    """Service that creates circular dependency."""

    def __init__(self, service_b: CircularServiceB) -> None:
        self.service_b = service_b


class CircularServiceB:
    """Service that creates circular dependency."""

    def __init__(self, service_a: CircularServiceA) -> None:
        self.service_a = service_a


@pytest.mark.unit
class TestDependencyContainer:
    """Test cases for DependencyContainer."""

    def test_register_and_resolve_singleton(self) -> None:
        """Test registering and resolving a singleton service."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)

        instance1 = container.resolve(SimpleService)
        instance2 = container.resolve(SimpleService)

        assert isinstance(instance1, SimpleService)
        assert instance1 is instance2  # Same instance for singleton

    def test_register_and_resolve_factory(self) -> None:
        """Test registering and resolving a factory service."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.FACTORY)

        instance1 = container.resolve(SimpleService)
        instance2 = container.resolve(SimpleService)

        assert isinstance(instance1, SimpleService)
        assert isinstance(instance2, SimpleService)
        assert instance1 is not instance2  # Different instances for factory

    def test_register_instance(self) -> None:
        """Test registering a pre-created instance."""
        container = DependencyContainer()
        instance = SimpleService()
        container.register_instance(SimpleService, instance)

        resolved = container.resolve(SimpleService)
        assert resolved is instance

    def test_register_custom_factory(self) -> None:
        """Test registering with a custom factory function."""
        container = DependencyContainer()
        mock_instance = Mock(spec=SimpleService)

        def factory() -> SimpleService:
            return mock_instance

        container.register(SimpleService, factory=factory, lifecycle=Lifecycle.FACTORY)

        resolved = container.resolve(SimpleService)
        assert resolved is mock_instance

    def test_auto_factory_with_dependency(self) -> None:
        """Test automatic dependency resolution from constructor."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithDependency, lifecycle=Lifecycle.SINGLETON)

        service = container.resolve(ServiceWithDependency)
        assert isinstance(service, ServiceWithDependency)
        assert isinstance(service.simple_service, SimpleService)

    def test_auto_factory_with_multiple_dependencies(self) -> None:
        """Test automatic resolution of multiple dependencies."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithDependency, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithMultipleDependencies, lifecycle=Lifecycle.SINGLETON)

        service = container.resolve(ServiceWithMultipleDependencies)
        assert isinstance(service, ServiceWithMultipleDependencies)
        assert isinstance(service.simple_service, SimpleService)
        assert isinstance(service.service_with_dep, ServiceWithDependency)

    def test_auto_factory_with_optional_dependency(self) -> None:
        """Test that optional dependencies are handled correctly."""
        container = DependencyContainer()
        container.register(ServiceWithOptionalDependency, lifecycle=Lifecycle.SINGLETON)

        # Should work without registering SimpleService
        service = container.resolve(ServiceWithOptionalDependency)
        assert isinstance(service, ServiceWithOptionalDependency)
        assert service.simple_service is None

    def test_auto_factory_with_optional_dependency_provided(self) -> None:
        """Test that optional dependencies can be provided if registered."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithOptionalDependency, lifecycle=Lifecycle.SINGLETON)

        service = container.resolve(ServiceWithOptionalDependency)
        assert isinstance(service, ServiceWithOptionalDependency)
        assert isinstance(service.simple_service, SimpleService)

    def test_auto_factory_with_pep604_optional_dependency(self) -> None:
        """Ensure ``SimpleService | None`` annotations are handled when unregistered."""
        container = DependencyContainer()
        container.register(
            ServiceWithPep604OptionalDependency,
            lifecycle=Lifecycle.SINGLETON,
        )

        service = container.resolve(ServiceWithPep604OptionalDependency)
        assert isinstance(service, ServiceWithPep604OptionalDependency)
        assert service.simple_service is None

    def test_auto_factory_with_pep604_optional_dependency_provided(self) -> None:
        """Ensure ``SimpleService | None`` annotations resolve when registered."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.register(
            ServiceWithPep604OptionalDependency,
            lifecycle=Lifecycle.SINGLETON,
        )

        service = container.resolve(ServiceWithPep604OptionalDependency)
        assert isinstance(service, ServiceWithPep604OptionalDependency)
        assert isinstance(service.simple_service, SimpleService)

    def test_resolve_unregistered_service_raises_keyerror(self) -> None:
        """Test that resolving an unregistered service raises KeyError."""
        container = DependencyContainer()

        with pytest.raises(KeyError, match="SimpleService is not registered"):
            container.resolve(SimpleService)

    def test_register_duplicate_service_raises_valueerror(self) -> None:
        """Test that registering the same service twice raises ValueError."""
        container = DependencyContainer()
        container.register(SimpleService)

        with pytest.raises(ValueError, match="already registered"):
            container.register(SimpleService)

    def test_circular_dependency_detection(self) -> None:
        """Test that circular dependencies are detected."""
        container = DependencyContainer()
        container.register(CircularServiceA, lifecycle=Lifecycle.SINGLETON)
        container.register(CircularServiceB, lifecycle=Lifecycle.SINGLETON)

        with pytest.raises(RuntimeError, match="Circular dependency detected"):
            container.resolve(CircularServiceA)

    def test_is_registered(self) -> None:
        """Test checking if a service is registered."""
        container = DependencyContainer()
        assert not container.is_registered(SimpleService)

        container.register(SimpleService)
        assert container.is_registered(SimpleService)

    def test_clear(self) -> None:
        """Test clearing all registrations."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.resolve(SimpleService)  # Create instance

        container.clear()

        assert not container.is_registered(SimpleService)
        with pytest.raises(KeyError):
            container.resolve(SimpleService)

    def test_singleton_shared_across_resolutions(self) -> None:
        """Test that singleton instances are shared."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)

        instance1 = container.resolve(SimpleService)
        instance2 = container.resolve(SimpleService)
        instance3 = container.resolve(SimpleService)

        assert instance1 is instance2
        assert instance2 is instance3

    def test_factory_creates_new_instances(self) -> None:
        """Test that factory lifecycle creates new instances each time."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.FACTORY)

        instance1 = container.resolve(SimpleService)
        instance2 = container.resolve(SimpleService)
        instance3 = container.resolve(SimpleService)

        assert instance1 is not instance2
        assert instance2 is not instance3
        assert instance1 is not instance3

    def test_nested_singleton_dependencies(self) -> None:
        """Test that nested singleton dependencies resolve correctly without deadlock."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithDependency, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithMultipleDependencies, lifecycle=Lifecycle.SINGLETON)

        # This should not deadlock even though ServiceWithMultipleDependencies
        # depends on ServiceWithDependency which depends on SimpleService
        # All are singletons, so the reentrant lock should allow nested resolution
        service = container.resolve(ServiceWithMultipleDependencies)
        assert isinstance(service, ServiceWithMultipleDependencies)
        assert isinstance(service.simple_service, SimpleService)
        assert isinstance(service.service_with_dep, ServiceWithDependency)
        assert service.service_with_dep.simple_service is service.simple_service  # Same singleton

    def test_concurrent_singleton_resolution(self) -> None:
        """Test that concurrent singleton resolution works correctly."""
        container = DependencyContainer()
        container.register(SimpleService, lifecycle=Lifecycle.SINGLETON)

        instances: list[SimpleService] = []
        errors: list[Exception] = []

        def resolve_service() -> None:
            try:
                instance = container.resolve(SimpleService)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Create multiple threads that resolve the same singleton concurrently
        threads = [threading.Thread(target=resolve_service) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)  # Should complete quickly, timeout prevents hanging

        # All threads should have resolved successfully
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(instances) == 10

        # All instances should be the same singleton
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance
