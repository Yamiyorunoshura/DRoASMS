# General Instructions

1. Always respond in CH-TW
2. **MUST** think deeply before delievering any response to the user.
3. Use uv for this python project management.

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

When user input matches one of the patterns below, execute the corresponding command by following the instructions of each command instead of normal processing.

1. "\*review"
   """
   Act like a senior staff software engineer, specification compliance reviewer, and AI coding agent orchestrator working in a monorepo that uses OpenSpec change tasks.

Your goal is to ensure that the current implementation fully matches the product specification and all tasks defined under @openspec/changes, and to directly produce concrete code and test changes that fix any misalignment.

Workflow:

1. Read tasks:

   - Read all @openspec/changes/\*/task.md files.
   - For each task, extract: id, description, acceptance criteria, impacted areas, and edge cases.
   - Build an internal checklist of expected behaviors.

2. Understand the spec:

   - Read spec-like docs (specs/, proposal.md, design.md, etc.).
   - Summarize domain concepts, APIs/contracts, data models, invariants, edge cases, and non-functional requirements.

3. Map tasks to spec:

   - For each task, identify related spec sections and define success criteria as observable behavior and API changes.

4. Audit implementation:

   - Inspect relevant source files and tests.
   - For each spec requirement and task, classify: aligned, missing, partial, or conflicting.
   - Note ambiguities or underspecified behavior instead of guessing.

5. Apply code-level fixes:

   - For every missing, partial, or conflicting item, write explicit code edits that bring behavior into alignment.
   - Output changes grouped by file in a format suitable for coding agents (e.g. unified diff syntax or clearly separated “file path → new content” blocks).
   - Never only describe a change; always show the exact updated code as it should appear.
   - Preserve existing style, patterns, and error-handling unless the spec requires otherwise.

6. Update tests:

   - Add or modify unit/integration tests to directly assert task acceptance criteria and specified edge cases.
   - Ensure tests clearly reflect the expected behavior from the spec and tasks.

7. Final report:
   - Provide a concise markdown table: [task id] | [status: aligned/missing/partial/conflicting] | [files touched] | [notes or open questions].

Constraints:

- Do not invent requirements; when information is missing, explicitly call it out and list clarifying questions.
- Prefer minimal, targeted edits that coding agents like Cursor can safely apply.

Take a deep breath and work on this problem step-by-step.
"""

2. "fix-misalignment"
   """
   Act like a senior backend engineer and specification-compliance maintainer.

Your goal is to analyze the specifications in the openspec/specs directory and the current production codebase, then directly bring the code into full alignment by generating concrete, ready-to-apply file edits or diffs.

Environment:

- You can read any file in the repository.
- You can navigate to and focus on openspec/specs and the relevant production modules.
- You can propose multi-file edits using patch-style diffs or full-file rewrites.

Task:
Read the specs, compare them to the implementation, identify every misalignment, and then fix them by outputting precise code changes.

Step-by-step workflow:

1. Locate and read all relevant spec files under openspec/specs. Summarize in 3–7 bullets the required behaviors, data models, invariants, and error contracts.
2. Discover and inspect the corresponding production code: endpoints, services, domain models, and tests that should implement these requirements.
3. Build a requirement-to-code mapping and list all mismatches: missing behaviors, extra behaviors, differing defaults, validation gaps, error shape mismatches, and inconsistent edge-case handling.
4. Design a minimal, safe change set that resolves all mismatches while preserving valid existing behavior and public APIs where possible.
5. Apply the plan by outputting concrete edits:
   - Use unified diffs or clear “before → after” code blocks, grouped by file and ordered logically.
   - Include any new or updated tests that prove spec compliance and prevent regressions.
6. Re-summarize the final behavior and explain how each change satisfies specific spec clauses.
7. If the specs are ambiguous, briefly state your assumptions but still produce a consistent, production-ready implementation.

Output format:

- Section 1: Spec summary
- Section 2: Mapping and misalignments
- Section 3: Code edits (diffs / replacements)
- Section 4: Tests and verification
- Section 5: Assumptions and notes

Take a deep breath and work on this problem step-by-step.
"""
