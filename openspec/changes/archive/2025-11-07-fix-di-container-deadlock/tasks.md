## 1. Investigation
- [x] 1.1 Identify root cause of stuck unit test
- [x] 1.2 Analyze threading lock usage in singleton resolution
- [x] 1.3 Research common deadlock patterns in dependency injection containers

## 2. Implementation
- [x] 2.1 Replace `threading.Lock` with `threading.RLock` in `DependencyContainer.__init__`
- [x] 2.2 Verify `_resolve_singleton` works correctly with reentrant lock
- [x] 2.3 Ensure thread-safety is maintained throughout the change

## 3. Testing
- [x] 3.1 Verify existing unit tests pass (especially `test_circular_dependency_detection`)
- [x] 3.2 Add test case for concurrent singleton resolution
- [x] 3.3 Add test case for nested singleton dependencies
- [x] 3.4 Run full test suite to ensure no regressions

## 4. Validation
- [x] 4.1 Run `openspec validate fix-di-container-deadlock --strict`
- [x] 4.2 Verify no linter errors
- [x] 4.3 Confirm tests complete without hanging
