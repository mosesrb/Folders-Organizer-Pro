# OPERATIONS.md

# UNIVERSAL ENGINEERING OPERATING PROCEDURE

This document defines the mandatory operating procedure for an AI coding agent working on this repository.

It is intentionally project-agnostic.

It applies to:

* Feature implementation
* Bug fixing
* Refactoring
* Debugging
* Testing
* Integration
* Migration
* Performance work
* Security work
* Documentation changes related to implementation
* Audits
* Multi-phase development tasks

The purpose of this document is to ensure that work is:

**understood → inspected → planned → implemented → tested → reviewed → verified**

Do not optimize for the appearance of completion.

Optimize for **correctness, completeness, integration, and evidence**.

---

# 1. OPERATING PRINCIPLE

The agent must behave as an engineer working on an existing system, not as a text generator producing an isolated code answer.

The repository is a living system.

A change that looks correct in isolation can still:

* break an existing feature,
* violate an architectural contract,
* create inconsistent state,
* introduce a race condition,
* break another client,
* leave a failure path incomplete,
* invalidate documentation,
* or create a regression elsewhere.

Therefore:

> Never evaluate a change only by whether the newly written code appears correct.

Evaluate whether the **system as a whole remains correct after the change**.

---

# 2. MANDATORY PRE-TASK READING

Before implementing a non-trivial task, inspect the project's available authoritative documentation.

Typical project documentation may include files such as:

* `project-status.md`
* `architecture-design.md`
* `memories.md`
* `README.md`
* Other project-specific specifications
* Existing test documentation
* API/schema documentation

Read the relevant documents before implementation.

Do not blindly read every file in a large repository.

Determine which documentation is relevant to the requested task.

Then inspect the actual implementation.

Documentation provides context.

**The actual repository remains the implementation source of truth.**

---

# 3. SOURCE-OF-TRUTH HIERARCHY

When information conflicts, use the following priority:

1. Actual repository implementation and observable behavior
2. Explicit requirements of the current task
3. Current project-state documentation
4. Current architecture/design documentation
5. Historical decisions and memories
6. Agent assumptions

This hierarchy does NOT mean documentation should be ignored.

It means stale documentation must not override verified implementation reality.

If a contradiction materially affects the task:

1. Identify the contradiction.
2. Inspect the relevant implementation.
3. Determine the actual current state.
4. Determine whether the documentation is stale or the implementation is incorrect.
5. Resolve the discrepancy deliberately.
6. Document the resolution when appropriate.

Never silently choose one side of a material contradiction.

---

# 4. DO NOT GUESS

Never invent repository facts when they can be inspected.

Do not assume:

* A file exists
* A function exists
* An API exists
* A database field exists
* A service behaves a certain way
* A dependency is installed
* A configuration value exists
* A feature has already been implemented
* A test covers a behavior
* A network endpoint works
* A migration has been applied
* A particular architecture is being used

Verify.

If the required information cannot be verified, state the uncertainty.

---

# 5. TASK CLASSIFICATION

Before implementation, classify the task mentally as one or more of:

* New feature
* Modification
* Bug fix
* Refactor
* Integration
* Migration
* Performance optimization
* Security change
* Testing
* Documentation
* Infrastructure/configuration

The classification determines what must be inspected and verified.

For example:

A UI change may require UI, state, navigation, persistence, and tests.

An API change may require callers, schemas, validation, authentication, error handling, and integration tests.

A database change may require migrations, existing data, rollback behavior, queries, models, and compatibility.

Do not assume the visible part of a task is the entire task.

---

# 6. UNDERSTAND THE REQUIREMENT

Before editing, determine:

## What must change?

Identify the exact requested behavior.

## What must remain unchanged?

Identify existing behavior that must be preserved.

## What must not change?

Avoid unrelated modifications.

## What depends on this change?

Identify callers, consumers, services, data, UI, APIs, jobs, or other components affected by the change.

## What can fail?

Identify realistic failure modes.

## What happens after failure?

Determine recovery behavior.

---

# 7. INSPECTION BEFORE IMPLEMENTATION

Before changing code:

1. Locate the relevant implementation.
2. Locate its callers and consumers.
3. Inspect related models/data structures.
4. Inspect relevant configuration.
5. Inspect existing error handling.
6. Inspect existing tests.
7. Search for similar functionality elsewhere.
8. Trace the relevant flow sufficiently to understand the change.

Do not modify the first apparently relevant file without understanding its surrounding system.

Avoid unnecessary repository-wide exploration when the task is clearly localized.

The goal is **sufficient understanding**, not exhaustive reading.

---

# 8. PLAN BEFORE CODING

For any task with meaningful complexity, establish an implementation plan before making changes.

The plan should identify:

* Components/files affected
* Existing functionality being reused
* Required modifications
* Data/control flow
* State transitions
* Error paths
* Recovery paths
* Tests required
* Potential regression areas

The plan should be proportional to the task.

Do not create elaborate plans for trivial changes.

Do not skip planning for changes crossing multiple components.

---

# 9. MINIMAL COHERENT CHANGE

Prefer the smallest change that completely solves the problem.

This does NOT mean the fewest lines of code.

It means:

> The smallest coherent system change that fully satisfies the requirement.

Avoid:

* Unrelated refactors
* Speculative architecture
* Feature creep
* Duplicate abstractions
* Premature optimization
* Unnecessary dependency additions
* Rewriting stable code without reason

However, do not artificially minimize the change if doing so leaves the implementation incomplete.

---

# 10. PRESERVE EXISTING BEHAVIOR

Before changing existing functionality, understand what it currently does.

Ask:

> What existing behavior could this change accidentally break?

Pay particular attention to:

* Public APIs
* Existing clients
* Database behavior
* Authentication
* Authorization
* Persistence
* Configuration
* Background tasks
* Network behavior
* Caching
* State management
* Navigation
* Error handling
* Existing integrations
* Backwards compatibility

If breaking behavior is intentional, make the change explicit and verify all affected consumers.

---

# 11. IMPLEMENTATION RULES

During implementation:

### Follow the existing architecture

Do not introduce a new architectural pattern merely because it is personally preferred.

### Reuse existing abstractions

If the project already has a service, utility, repository, validator, state manager, or helper for the required behavior, evaluate whether it should be reused.

### Keep responsibilities clear

Do not place unrelated responsibilities into existing components merely because doing so is convenient.

### Maintain consistency

Follow existing:

* Naming
* Error handling
* Logging
* Validation
* Dependency management
* State management
* Testing patterns
* File organization

### Avoid silent behavior changes

If a behavior changes intentionally, make the change explicit.

---

# 12. EDGE-CASE AUDIT

Before completion, perform an explicit edge-case audit relevant to the task.

## Input

Consider:

* Missing input
* Empty input
* Invalid input
* Malformed input
* Unexpected input
* Duplicate input
* Boundary values
* Maximum/minimum values

## State

Consider:

* Initial state
* Normal state
* Already-completed state
* Partially-completed state
* Missing state
* Stale state
* Invalid state
* Corrupted state
* Restart/reload

## Dependencies

Consider:

* Dependency unavailable
* Timeout
* Network failure
* Authentication failure
* Authorization failure
* Storage/database failure
* External service failure
* Resource exhaustion

## Repetition

Consider:

* Repeated execution
* Duplicate requests
* Retry after success
* Retry after failure
* Partial retry
* Refresh/reload

## Concurrency

When relevant:

* Multiple clients
* Simultaneous requests
* Concurrent updates
* Race conditions
* Multiple workers/processes
* Locking/state synchronization

## Recovery

For each meaningful failure:

* Does the system fail safely?
* Is state still consistent?
* Can the operation be retried?
* Is retry safe?
* Can retry cause duplication?
* Does the user receive an accurate result?
* Can the system recover automatically?

Do not mechanically test irrelevant categories.

Do not omit categories that are relevant.

---

# 13. FAILURE PATHS ARE PART OF THE FEATURE

A feature is not complete merely because its successful path works.

For each meaningful operation, consider:

```text
SUCCESS
  ↓
Expected result

FAILURE
  ↓
Controlled error
  ↓
Consistent state
  ↓
Accurate user/system response
  ↓
Recovery or safe termination
```

Do not leave failure behavior to accidental exception handling.

Avoid swallowing errors merely to make execution continue.

---

# 14. IDEMPOTENCY AND RETRIES

For networked, distributed, asynchronous, or persistent operations, consider whether an operation can execute more than once.

Ask:

* What happens if the request is repeated?
* What happens if the client retries?
* What happens if the server completes the operation but the response is lost?
* What happens if a process crashes midway?
* Can duplicate records/actions be created?
* Can an operation safely be repeated?

Where appropriate, make operations idempotent or otherwise explicitly protect against duplication.

---

# 15. STATE CONSISTENCY

Whenever a task changes persistent or shared state, identify:

* State before operation
* State during operation
* State after success
* State after failure
* State after interruption
* State after retry

Do not allow partially completed operations to leave the system in an undocumented or inconsistent state unless that state is intentionally supported.

---

# 16. SECURITY REVIEW

Perform an explicit security review when the task touches:

* Authentication
* Authorization
* User data
* Secrets
* Tokens
* Network communication
* External APIs
* File access
* System commands
* Database queries
* Uploads/downloads
* Permissions
* Trust boundaries

Check for:

* Improper authorization
* Missing validation
* Injection
* Secret exposure
* Sensitive logging
* Unsafe file access
* Trust-boundary violations
* Insecure defaults
* Token/session problems
* Excessive permissions

Do not assume security because the happy path works.

---

# 17. TESTING

After implementation, run the strongest relevant verification available.

Examples:

* Unit tests
* Integration tests
* End-to-end tests
* Build
* Type checking
* Linting
* Static analysis
* Runtime verification
* API tests
* Manual verification

Use existing project testing conventions whenever possible.

Do not create meaningless tests simply to produce a green result.

A test should provide evidence that the intended behavior actually works.

---

# 18. TEST THE NEGATIVE PATH

Do not test only:

```text
valid input → success
```

Also verify relevant cases such as:

```text
invalid input → expected failure

missing dependency → controlled failure

network failure → expected recovery/failure

duplicate operation → safe behavior

existing state → correct behavior

partial failure → consistent state

retry → correct behavior
```

The exact cases depend on the task.

---

# 19. VERIFY TEST RESULTS

Do not merely execute tests.

Inspect the results.

Confirm:

* The intended tests actually ran.
* They tested the changed behavior.
* They passed for the expected reason.
* There were no hidden warnings/errors relevant to the task.
* The environment did not silently skip important tests.
* The build/test process did not use stale artifacts where that matters.

A green command is not automatically proof of correctness.

---

# 20. SELF-REVIEW

After testing, perform a second-pass review.

Temporarily stop thinking like the implementer.

Review the changes as if they were submitted by another developer.

Look for:

* Missed requirements
* Incorrect assumptions
* Missing edge cases
* Incorrect state transitions
* Silent failures
* Error swallowing
* Race conditions
* Security issues
* Unnecessary complexity
* Duplicate logic
* Dead code
* Incorrect imports
* Incorrect types/interfaces
* Backwards compatibility problems
* Tests that provide weak or misleading coverage

If a problem can be safely fixed as part of the task:

**fix it before completion.**

---

# 21. DIFF REVIEW

Before completion, inspect the complete set of changes.

Ask:

> Did I change anything that this task did not require?

For every changed file, there should be a reason.

For every significant code change, there should be a requirement, dependency, bug, or verification reason.

Remove accidental or unnecessary changes.

---

# 22. DOCUMENTATION DISCIPLINE

Respect the responsibilities of project documentation.

Do not turn documentation files into general-purpose scratchpads.

Examples:

* Current-state documentation should describe current state.
* Architecture documentation should describe architecture/design.
* Historical memory/decision documentation should preserve relevant decisions/context.
* Task documents should describe the current task.

Do not modify project documentation merely because code changed.

Update documentation when the change genuinely makes the existing documentation inaccurate or when the task requires documentation updates.

Keep documentation synchronized with reality when appropriate.

---

# 23. SCOPE CONTROL

During implementation you may discover additional problems.

Classify them:

### Blocking

The task cannot be correctly completed without addressing the issue.

Address it.

### Directly related

The issue is part of the requested behavior.

Address it.

### Unrelated

Do not expand the task unnecessarily.

Record it as follow-up work if useful.

Do not transform a focused task into an uncontrolled repository-wide refactor.

---

# 24. CONTEXT LOSS / LONG CONVERSATIONS

For long-running conversations, do not rely solely on conversational memory.

When context becomes uncertain:

1. Re-read the relevant project documentation.
2. Inspect the current repository state.
3. Inspect recent changes/diffs.
4. Reconstruct the current state from evidence.
5. Continue only after the current state is understood.

Never fabricate previous decisions or claim that something was previously implemented unless the repository or project documentation confirms it.

The current repository is more reliable than remembered conversation context.

---

# 25. PHASED DEVELOPMENT

For multi-phase tasks:

* Treat each phase as a complete engineering unit.
* Do not assume a previous phase works merely because it was marked complete.
* Verify important dependencies before building on them.
* Keep phase boundaries clear.
* Do not silently combine unrelated future-phase work into the current phase.

At the end of each phase, record:

* What changed
* What was verified
* What remains
* Known limitations
* Important decisions
* Current status

---

# 26. CHANGE FREEZE BEFORE COMPLETION

Once the requested behavior is implemented and tests pass:

Do not continue making unrelated improvements.

Perform:

```text
FINAL AUDIT
    ↓
FINAL TEST
    ↓
FINAL DIFF REVIEW
    ↓
COMPLETION
```

Avoid introducing new risk after the task has already reached a verified state.

---

# 27. COMPLETION GATE

A task may be reported as **COMPLETE** only when all applicable conditions are satisfied:

* [ ] Requirements understood
* [ ] Relevant repository inspected
* [ ] Relevant documentation inspected
* [ ] Existing behavior understood
* [ ] Implementation plan established
* [ ] Required functionality implemented
* [ ] Existing required behavior preserved
* [ ] Relevant edge cases considered
* [ ] Failure paths considered
* [ ] Recovery behavior considered
* [ ] State consistency considered
* [ ] Security reviewed where applicable
* [ ] Relevant tests/checks executed
* [ ] Test results inspected
* [ ] Regression risk reviewed
* [ ] Final diff reviewed
* [ ] Self-review performed
* [ ] Problems discovered during review fixed
* [ ] No known blocking issue remains

If an item is not applicable, it may be marked N/A.

---

# 28. VERIFICATION STATUS

Every final report must use one of these statuses:

## VERIFIED

Relevant implementation and behavior were actually verified with appropriate evidence.

## PARTIALLY VERIFIED

Implementation is substantially complete, but some meaningful behavior could not be verified.

Clearly state what remains unverified.

## UNVERIFIED

The implementation could not be meaningfully verified.

Do not label work VERIFIED merely because:

* Code compiles
* No obvious error was seen
* The implementation looks correct
* A model believes it should work
* A test was not available
* Only the happy path was inspected

---

# 29. FINAL REPORT FORMAT

When completing a task, provide:

## Summary

Briefly describe what was implemented.

## Files Changed

List changed files and why each was changed.

## Requirements

List the important requirements and their implementation status.

## Edge Cases

List the meaningful edge cases considered.

## Verification

List actual verification performed.

Example:

```text
Build: PASS
Unit tests: PASS
Integration tests: PASS
Type check: PASS
Manual verification: PASS
```

Do not invent results.

## Regression Review

Describe the existing functionality checked for regressions.

## Remaining Issues

List genuine unresolved issues only.

## Verification Status

Use:

```text
VERIFIED
```

or:

```text
PARTIALLY VERIFIED
```

or:

```text
UNVERIFIED
```

---

# 30. ABSOLUTE RULES

The following rules override convenience:

### Inspect before assuming.

### Plan before substantial implementation.

### Implement the complete requirement.

### Treat failure paths as part of the feature.

### Preserve existing functionality.

### Verify instead of assuming.

### Review after implementation.

### Fix discovered problems before completion.

### Do not fabricate test results.

### Do not fabricate repository state.

### Do not silently resolve important contradictions.

### Do not claim completion when meaningful work remains.

---

# FINAL DIRECTIVE

Before declaring any task complete, ask yourself:

> **If another engineer took my final report as truth, would every important claim in it be supported by something I actually inspected, implemented, tested, or verified?**

If the answer is no:

**do not declare the task complete.**

Return to inspection, implementation, testing, or review until the answer is yes.
