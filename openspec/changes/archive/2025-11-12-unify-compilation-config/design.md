## Context

DRoASMS currently has compilation configuration scattered across multiple files:
- `pyproject.toml`: Contains mypyc configuration for economy modules
- `mypc.toml`: Specialized configuration for governance modules
- `Makefile`: Compilation targets and orchestration

This separation creates maintenance complexity and makes it difficult for new developers to understand the compilation process.

## Goals / Non-Goals

**Goals:**
- Unify all compilation configuration in pyproject.toml
- Maintain current performance optimizations
- Provide consistent compilation interface
- Support gradual migration with backward compatibility
- Enable performance monitoring and regression detection

**Non-Goals:**
- Force all modules to use the same compilation backend
- Change existing performance optimizations
- Break current development workflows during transition

## Decisions

**Decision: Use pyproject.toml as single source of truth**
- Leverages Python project standard
- Native tool support (Poetry, Hatch, etc.)
- Human-readable TOML format
- Integration with Python packaging ecosystem

**Decision: Multi-backend support with unified interface**
- Preserve existing mypyc optimizations for economy modules
- Keep mypc for governance modules with proven performance
- Abstract backend differences through unified API
- Allow future backend additions without major changes

**Alternatives considered:**
- Force mypyc for all modules: Would lose governance optimizations
- Custom configuration format: Would break tooling support
- Separate configuration files: Doesn't solve the original problem

## Risks / Trade-offs

**Performance regression risk** → Mitigation: Keep module-specific optimization parameters, establish performance baselines
**Migration complexity** → Mitigation: Gradual transition period, automated migration tools
**Tool compatibility** → Mitigation: Maintain backward compatibility during transition, comprehensive testing

## Migration Plan

**Phase 1: Configuration unification (1 week)**
- Migrate mypc.toml settings to pyproject.toml [tool.unified-compiler]
- Create configuration validation and migration tools
- Maintain backward compatibility

**Phase 2: Script integration (1 week)**
- Develop unified compilation script
- Update existing scripts to use unified configuration
- Implement performance monitoring

**Phase 3: Cleanup (0.5 week)**
- Remove obsolete configuration files
- Update documentation
- Final testing and validation

**Rollback strategy:** Keep backup scripts and configuration files; implement quick revert functionality

## Open Questions

- Should we establish performance regression thresholds (e.g., 5% degradation)?
- How to handle module-specific compiler flags that don't fit unified schema?
- Should we implement automatic configuration migration or manual process?
