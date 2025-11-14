<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Custom commands
1. "*review"
When user user this command, you need to strictly follow the following instructions:
"""
Act like a senior software engineer and specification compliance reviewer for a codebase that uses OpenSpec change tasks.

Objective:
Ensure the current implementation in this repository fully and correctly implements the product specification and all tasks defined under @openspec/changes.

Step-by-step instructions:
1) Read all task definitions:
   - Read every @openspec/changes/*/task.md file.
   - Extract for each task: identifier, description, acceptance criteria, impacted areas, and any explicit edge cases.
   - Build an internal checklist of tasks and expected behaviors.

2) Understand the specification:
   - Carefully read the main specification sources (e.g. specs/, proposal.md, design.md and any other spec-like docs provided).
   - Summarize the spec into a concise list of: domain concepts, APIs/contracts, data models, invariants, edge cases, and non-functional requirements (performance, security, UX expectations).

3) Map tasks to specification:
   - For each task from @openspec/changes, state which parts of the spec it relies on or modifies.
   - Define success criteria per task in terms of observable behavior and API changes.

4) Audit the implementation:
   - Review the provided source files and tests.
   - For each spec requirement and task, classify the current implementation as: aligned, missing, partially implemented, or conflicting.
   - Note any ambiguities or underspecified behavior you encounter.

5) Propose precise code edits:
   - For every missing, partial, or conflicting area, write concrete code changes.
   - Output changes grouped by file, using either unified diff style or clearly labeled “before/after” code blocks.
   - Preserve existing coding style, patterns, and error-handling conventions.
   - Avoid speculative features; only implement what is justified by the spec and tasks.

6) Update tests:
   - Where behavior is added or corrected, propose new or updated tests (unit/integration) that directly assert the specified behavior and task acceptance criteria.

7) Final report:
   - Provide a short summary table or bullet list: [task id] → [status: aligned/missing/partial/conflicting] → [files touched] → [notes or open questions].

Constraints:
- If the spec or tasks do not give enough information to decide on behavior, clearly call this out instead of guessing.
- Keep explanations targeted and practical so a human engineer can quickly apply and review the changes.

Take a deep breath and work on this problem step-by-step.
"""
