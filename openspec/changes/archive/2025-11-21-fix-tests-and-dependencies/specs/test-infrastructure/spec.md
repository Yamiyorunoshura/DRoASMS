## MODIFIED Requirements

### Requirement: Pytest Configuration Management
The test infrastructure SHALL provide pytest configuration with all required markers and settings properly defined.

#### Scenario: Test Collection Without Markers Warnings
- **WHEN** pytest is executed without specific test selection
- **THEN** all tests shall be collected successfully without "Unknown pytest.mark.contract" warnings
- **AND** the contract marker shall be properly defined in pyproject.toml

#### Scenario: Test Suite Execution
- **WHEN** pytest runs the full test suite
- **THEN** all 29 test files shall be collected without import errors
- **AND** test execution shall complete with 98%+ coverage maintained

## ADDED Requirements

### Requirement: Cython Import Resolution
The test infrastructure SHALL ensure all Cython extensions can be imported correctly by test modules.

#### Scenario: Suspect Class Import
- **WHEN** src/bot/services/justice_service.py imports from Cython extensions
- **THEN** the Suspect-related classes shall be successfully imported from the correct module
- **AND** no ImportError shall be raised during test collection

#### Scenario: Cython Extension Compilation
- **WHEN** pytest discovers tests requiring Cython extensions
- **THEN** all required Cython modules shall be compiled and importable
- **AND** tests shall have access to all Cython-defined classes and functions

### Requirement: Dependency Compatibility Validation
The test infrastructure SHALL validate that all dependency updates remain compatible with existing test patterns.

#### Scenario: Ruff Compatibility Testing
- **WHEN** ruff is updated to version 0.7.x
- **THEN** existing linting rules shall continue to pass
- **AND** any new rules shall be addressed without breaking existing code patterns

#### Scenario: Pytest Ecosystem Updates
- **WHEN** pytest and related packages are updated
- **THEN** all existing test markers, fixtures, and assertions shall continue to function
- **AND** test discovery and execution patterns shall remain unchanged

## REMOVED Requirements

### Requirement: Legacy Test Collection Workarounds
**Reason**: The import errors that required workarounds are being fixed at the source.
**Migration**: Remove any test collection workarounds once the Suspect import is resolved.
