## MODIFIED Requirements
### Requirement: Thread-Safe Singleton Resolution
The dependency injection container SHALL provide thread-safe singleton resolution that prevents deadlocks when factories recursively resolve other singleton dependencies.

#### Scenario: Singleton with singleton dependency
- **WHEN** a singleton service's factory function resolves another singleton dependency
- **THEN** the resolution completes without deadlock
- **AND** both singletons are correctly instantiated and cached

#### Scenario: Circular dependency detection with singletons
- **WHEN** circular dependencies are detected during singleton resolution
- **THEN** a RuntimeError is raised with a clear cycle description
- **AND** no deadlock occurs during the detection process

#### Scenario: Concurrent singleton resolution
- **WHEN** multiple threads simultaneously resolve the same singleton
- **THEN** only one instance is created
- **AND** all threads receive the same instance
- **AND** no deadlock occurs
