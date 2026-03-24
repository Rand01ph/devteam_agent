<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles:
  - template principle 1 -> I. Library-First Delivery
  - template principle 2 -> II. Strict Test-Driven Development
  - template principle 3 -> III. Functional Core, Imperative Shell
  - template principle 4 -> IV. Explicit Contracts at Every Boundary
  - template principle 5 -> V. Incremental, Non-Destructive Evolution
- Added sections:
  - Engineering Constraints
  - Workflow & Quality Gates
- Removed sections:
  - None
- Templates requiring updates:
  - ✅ updated .specify/templates/plan-template.md
  - ✅ updated .specify/templates/spec-template.md
  - ✅ updated .specify/templates/tasks-template.md
  - ✅ updated README.md
  - ✅ updated AGENTS.md
  - ✅ updated .agents/skills/speckit-tasks/SKILL.md
  - ✅ verified no files matched .specify/templates/commands/*.md
- Follow-up TODOs:
  - None
-->
# DevTeam Agent Constitution

## Core Principles

### I. Library-First Delivery
Every feature MUST begin as a standalone library or library-like module with a
clear, documented purpose and stable interface. Agent tools, CLI entrypoints,
web handlers, and scheduled workflows MUST compose those libraries rather than
embedding business rules inline. A feature is not complete until its core logic
can be exercised independently of the conversational runtime.

Rationale: library-first boundaries keep core behavior reusable, testable, and
replaceable as the surrounding agent surface evolves.

### II. Strict Test-Driven Development
All production behavior MUST be developed with strict TDD. The required cycle is
red, green, refactor: write the smallest failing test first, implement the
minimal change to pass it, then refactor with tests green. New behavior, bug
fixes, and contract changes MUST start with tests that fail for the intended
reason before production code is introduced or modified.

Rationale: the repository automates team reporting flows and external
integrations, so regression detection must happen before implementation rather
than after the fact.

### III. Functional Core, Imperative Shell
Business rules, parsing, transformations, and report assembly SHOULD default to
pure functions with explicit inputs and outputs. Side effects such as file I/O,
network access, logging, and time acquisition MUST be isolated at the system
edges behind small orchestration layers. Mutable shared state, hidden globals,
and class-heavy designs require explicit justification in the implementation
plan.

Rationale: a functional core reduces accidental coupling, makes tests smaller,
and improves confidence when evolving parsing and summarization workflows.

### IV. Explicit Contracts at Every Boundary
Each library boundary MUST define its inputs, outputs, and failure modes in a
way that is deterministic and easy to validate. Parsing rules, file formats,
tool arguments, and integration adapters MUST prefer explicit schemas or
well-documented structures over inferred behavior. Breaking contract changes
MUST be reflected in tests, documentation, and migration notes in the same
change.

Rationale: this project coordinates agent tools, report files, and external
systems; explicit contracts are the only reliable way to keep those boundaries
safe as features change.

### V. Incremental, Non-Destructive Evolution
Changes MUST preserve existing user-authored data unless the user explicitly
requests destructive behavior. Implementations SHOULD favor small, composable
steps that keep the system working after each story is delivered. If a simpler
design is available, teams MUST prefer it unless the implementation plan records
why additional complexity is necessary.

Rationale: weekly report data is user-managed content; the safest path is to
evolve behavior incrementally and protect existing material by default.

## Engineering Constraints

- Python modules implementing new behavior MUST expose a library entrypoint
  before any tool-facing wrapper is added.
- Tests for pure logic SHOULD live in unit tests; adapter and boundary behavior
  MUST be covered by contract or integration tests as appropriate.
- Time, filesystem paths, environment configuration, and network clients MUST be
  injectable or otherwise controllable in tests.
- When object-oriented state is used, the design review MUST explain why a pure
  functional alternative was insufficient.

## Workflow & Quality Gates

1. Specifications and plans MUST identify the target library/module, the
   external adapters that call it, and the tests that will be written first.
2. Implementation plans MUST fail constitution review if they skip the
   library-first boundary, omit the TDD sequence, or rely on avoidable mutable
   state.
3. Task breakdowns MUST schedule failing tests before implementation tasks for
   each user story.
4. Reviews MUST verify that user-authored report content is preserved unless a
   destructive change was explicitly approved.
5. Documentation for new behavior MUST describe the core library API and any
   contract changes introduced by the feature.

## Governance

This constitution supersedes conflicting local habits and default templates.
Amendments require an explicit user request or approved project decision, a
written explanation of the change, and updates to affected templates or runtime
guidance in the same change set.

Versioning policy follows semantic versioning for governance:
- MAJOR: removes or redefines a core principle in a backward-incompatible way.
- MINOR: adds a principle, section, or materially stronger requirement.
- PATCH: clarifies wording without changing expected behavior.

Compliance review is mandatory for every feature plan, task list, and code
review. Any exception MUST be documented in the relevant plan under complexity
or risk tracking, with rationale and a bounded follow-up path.

**Version**: 1.0.0 | **Ratified**: 2026-03-24 | **Last Amended**: 2026-03-24
