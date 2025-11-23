## Context

This change addresses critical technical debt identified in the DRoASMS codebase. The primary blocking issue is a Cython import error preventing the test suite from running, while secondary issues involve outdated dependencies and security vulnerabilities. The project uses a sophisticated architecture with Cython extensions, mypyc compilation, and comprehensive testing infrastructure.

## Goals / Non-Goals

**Goals**:
- Restore full test suite functionality (currently 0 tests can run due to import error)
- Update dependencies to current stable versions
- Resolve security vulnerabilities
- Maintain 98%+ test coverage threshold
- Preserve all existing functionality without breaking changes

**Non-Goals**:
- Architecture refactoring (focus on fixes only)
- New feature development
- Performance optimization beyond what dependencies provide
- Major version bumps that would require code changes

## Decisions

### 1. Suspect Import Resolution
**Decision**: Update import path in `justice_service.py` from `council_governance_models` to `state_council_models`

**Rationale**:
- `SuspectProfile` and related classes already exist in `state_council_models.pyx`
- This matches the semantic domain - suspects are state-level governance concerns, not council-level
- Minimal code change with no architectural impact
- Avoids duplicating classes across modules

**Alternatives considered**:
- Add `Suspect` class to `council_governance_models.pyx` (rejected: duplication)
- Create shared base module (rejected: over-engineering for single class issue)
- Refactor entire Cython module structure (rejected: out of scope)

### 2. Dependency Update Strategy
**Decision**: Incremental updates with validation at each major version jump

**Rationale**:
- Major version updates (ruff 0.5.7→0.7.x, pytest 8.x) may introduce breaking changes
- Phased approach allows rollback if issues arise
- Maintains project stability during updates

**Update Priority**:
1. ruff (linting infrastructure)
2. pytest ecosystem (testing foundation)
3. security-focused dependencies
4. remaining updates

### 3. Safety Validation
**Decision**: Comprehensive compatibility testing after each update batch

**Rationale**:
- Cython compilation sensitive to dependency versions
- MyPy strict mode may fail with new type definitions
- discord.py integration requires careful validation

## Risks / Trade-offs

### Risk 1: Major Dependency Breaking Changes
**Impact**: ruff 0.7.x may introduce new linting rules that require code changes
**Mitigation**: Review ruff changelog, address violations incrementally, use `--fix` where appropriate

### Risk 2: Cython/Mypyc Compilation Issues
**Impact**: Updated dependencies may break compilation of performance-critical extensions
**Mitigation**: Test compilation in isolated environment, maintain fallback versions

### Risk 3: Test Coverage Regression
**Impact**: Dependency updates may change coverage calculation or introduce new test requirements
**Mitigation**: Compare coverage reports before/after, adjust thresholds only if justified

### Trade-off: Update Pace vs Stability
**Chosen approach**: Prioritize stability with measured, validated updates
**Alternative**: Rapid updates (rejected: potential for major disruptions)

## Migration Plan

### Phase 1: Critical Fix (Immediate)
1. Fix Suspect import error
2. Verify pytest collection works
3. Add missing contract marker

### Phase 2: Core Dependencies (Priority)
1. Update ruff ecosystem
2. Update pytest ecosystem
3. Address security vulnerabilities
4. Validate test suite functionality

### Phase 3: Remaining Updates (Stability)
1. Update remaining dependencies
2. Code quality fixes (MyPy, formatting)
3. Full compatibility validation
4. Documentation updates if needed

### Rollback Strategy
- Maintain `pyproject.toml.backup` before any changes
- Git commit after each successful phase
- Revert individual phases if major issues arise
- Use semantic versioning to track changes

## Open Questions

1. **ruff 0.7.x Compatibility**: Will new ruff rules require code changes beyond auto-fixes?
2. **pytest 8.x Impact**: Any deprecations affecting the current test structure?
3. **Cython Compilation**: Will updated Python/compiler interfaces affect extension builds?
4. **Performance Impact**: Will dependency updates affect bot startup time or memory usage?
