## Context

This change adds a Justice Department to the State Council panel, completing the government structure. Currently, the State Council has four departments (Interior Affairs, Finance, Homeland Security, and Central Bank) but lacks a judicial branch.

Key constraints:
- Must integrate with existing State Council UI patterns
- Must maintain data consistency with existing arrest/release system
- Must follow existing permission and audit logging patterns
- Must not break existing economic command functionality

Stakeholders:
- State Council leaders (need UI access)
- Homeland Security (release logic changes)
- Finance/Admin (audit trail consumers)

## Goals / Non-Goals

Goals:
- Provide Justice Department with economic operation capabilities (transfers, balance adjustments)
- Enable suspect management and prosecution workflows
- Prevent automatic release of charged suspects
- Maintain consistency with existing department patterns

Non-Goals:
- Changing existing department permissions or workflows
- Modifying core economic system behavior
- Adding new currency types or economic mechanics
- Creating separate Justice Department commands (integrating into State Council panel instead)

## Decisions

**Decision 1: Use existing State Council panel UI pattern**
- What: Add Justice Department as a new tab in existing `/state-council` command
- Why: Consistency with existing UI reduces learning curve and code duplication
- Alternatives considered: Separate `/justice` command - adds complexity and fragmentation

**Decision 2: Create separate suspects table instead of modifying existing arrest system**
- What: New `governance.suspects` table for tracking prosecution status
- Why: Isolates new functionality, preserves existing data integrity, enables historical tracking
- Alternatives considered: Adding columns to existing arrest tables - risks data corruption and complicates queries

**Decision 3: Cascade prosecution status check in Homeland Security release flow**
- What: Modify release logic to check prosecution status before allowing release
- Why: Ensures judicial decisions are respected, prevents accidental releases
- Alternatives considered: Separate release mechanism - would require duplicate code

**Decision 4: Implement JusticeService as separate service layer**
- What: Create dedicated service for Justice Department operations
- Why: Clear separation of concerns, easier testing, follows existing service pattern
- Alternatives considered: Adding methods to existing services - would create coupling

**Decision 5: Use existing economic command patterns for Justice Department access**
- What: Extend transfer/adjust commands to recognize Justice Department role
- Why: Leverages existing, tested code; maintains consistency
- Alternatives considered: Separate economic commands - unnecessary duplication

## Risks / Trade-offs

- **Risk: Database migration failure** → Mitigation: Test migration in staging, have rollback script ready
- **Risk: Concurrent suspect status updates** → Mitigation: Use database transactions and optimistic locking
- **Risk: Performance issues with large suspect lists** → Mitigation: Implement pagination, add database indexes
- **Risk: Circular dependencies between services** → Mitigation: Clear service boundaries, use dependency injection
- **Trade-off**: Added complexity to Homeland Security release flow - but necessary for judicial independence

## Migration Plan

**Deployment Steps:**
1. Run database migration to add suspects table
2. Deploy new JusticeService
3. Update economic commands (transfer/adjust)
4. Deploy State Council panel changes
5. Update Homeland Security release logic
6. Verify all components in staging

**Rollback Plan:**
- Database: Restore from backup if migration fails
- Code: Rollback to previous version via git revert
- Feature flags: Can disable Justice Department UI if issues arise

**Monitoring:**
- Track suspect table size and query performance
- Monitor Justice Department command usage
- Watch for increased error rates in release flow

## Open Questions

- Should we notify members when they are charged? (privacy vs transparency)
- Do we need a statute of limitations for charges? (gameplay balance)
- Should Justice Department have a budget limit like other departments? (economic balance)
- Do we need a way for higher authorities to overturn charges? (governance hierarchy)
