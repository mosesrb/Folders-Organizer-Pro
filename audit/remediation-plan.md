# Folders Organizer Pro — Remediation Plan

**Prepared:** 2026-08-24  
**Source baseline:** `main` at `98e29627cb3998a9f8086f9ca26f59074e2c94eb`  
**Input:** `audit/findings.md`  
**Current release recommendation:** Do not release

## 1. Objective

Close the audit’s 1 Critical, 11 High, and 6 Medium findings, establish
regression coverage for every repaired safety boundary, and produce new Windows
artifacts traceable to a newly versioned, audited commit.

Remediation is complete only when the final release gate in Section 8 passes.
A green build or the existing 33 tests alone is not sufficient.

## 2. Working Rules

- Perform all mutating tests inside generated disposable workspaces.
- Do not test destructive behavior against real user folders or system paths.
- Add a failing regression test before or with every fix.
- Validate and canonicalize paths at the backend boundary; never rely on the UI
  to enforce safety.
- Treat source and destination containment, collision handling, confirmation,
  dry-run, and undo as one operation contract.
- Do not publish replacement artifacts until all Critical and High findings are
  closed and independently retested.
- Keep remediation commits focused by workstream so findings can be reviewed
  and reverted independently.

## 3. Recommended Architecture Changes

Before patching individual methods, introduce shared safety primitives to avoid
repeating inconsistent checks:

1. **Canonical path policy**
   - Normalize Windows device/extended/UNC forms.
   - Resolve symlinks and junctions where possible.
   - Reject volume roots, share roots, protected system paths, alternate device
     namespaces, and paths outside approved roots.
   - Provide `validate_workspace(path)`, `validate_source(path, workspace)`, and
     `validate_destination(path, workspace)` helpers.

2. **Operation registry**
   - Define each exposed operation’s mutating, destructive, dry-run,
     confirmation, undo, recursive, and path-scope capabilities in one backend
     registry shared with or returned to the frontend.
   - Remove duplicated frontend lists such as `UNDOABLE_OPS`,
     `DESTRUCTIVE_OPS`, and `RECURSIVE_CAPABLE_OPS` as independent sources of
     truth.

3. **Collision-safe output allocator**
   - Reserve unique destinations across an entire batch before mutation.
   - Write generated media/archives to unique temporary files.
   - Validate output, then atomically promote it to a destination known to be
     free.
   - Never use timestamps as the only collision fallback.

4. **Transactional operation journal**
   - Preflight batches before mutation where practical.
   - Persist journal entries incrementally and atomically before or immediately
     after each filesystem change.
   - Preserve partial history on failure and report completed, skipped, and
     failed items separately.
   - Bind journal entries to the selected workspace and the exact objects the
     application created or moved.

5. **Safe undo model**
   - Do not execute arbitrary actions from an editable JSON file.
   - Store history in application-controlled local state, or authenticate and
     strictly validate workspace history.
   - Track file identity, operation ID, expected path, size/hash, and creation
     state.
   - Refuse undo if a target changed after the operation.
   - Send deleted outputs to the Recycle Bin and require confirmation for
     destructive undo.

## 4. Remediation Workstreams

### Workstream A — Critical Undo Containment

**Findings:** FOP-AUD-001  
**Priority:** P0 — begin immediately; block all releases

#### Implementation

1. Disable loading/executing legacy history until it passes a strict schema and
   containment check.
2. Reject unknown actions, missing fields, relative paths, alternate Windows
   namespaces, protected roots, and targets outside the operation’s authorized
   scope.
3. Prevent `create`/`copy` undo from deleting a target unless the journal proves
   the application created that exact object and its identity is unchanged.
4. Replace permanent `unlink`/`rmtree` behavior with safe Recycle Bin handling.
5. Preserve failed history for retry or manual recovery; never clear all entries
   after a partial undo.
6. Add an explicit destructive-undo confirmation showing exact target count and
   workspace.
7. Decide how to migrate or quarantine existing `.organizer_history.json`
   files. Default to quarantine/fail closed rather than executing ambiguous
   legacy entries.

#### Required tests

- Crafted history cannot delete or move a sibling path.
- Crafted history cannot target a system directory, drive root, UNC root,
  junction escape, or extended namespace path.
- Unknown/malformed actions fail closed without mutation.
- Modified outputs are not removed by Undo.
- Partial undo retains unresolved entries.
- Valid move/create/copy histories still restore disposable fixtures correctly.
- The UI does not enable Undo for rejected/quarantined history.

#### Acceptance criteria

- The reproduction `untrusted_history_external_delete` leaves the sibling
  victim intact and returns a clear safety error.
- No undo code permanently deletes user-visible files or directories.
- FOP-AUD-001 is independently retested and closed.

### Workstream B — Path Policy and Workspace Containment

**Findings:** FOP-AUD-002, FOP-AUD-007, path-scope portion of FOP-AUD-015  
**Priority:** P0

#### Implementation

1. Add the shared Windows canonical path policy described in Section 3.
2. Apply it to every exposed API method and every computed final destination,
   not only the initially selected workspace.
3. Sanitize custom rule folder names. Permit deliberate nested folders only as
   validated relative paths beneath the workspace.
4. Validate `folder_names`, archive extensions/output paths, backup source and
   destination, media paths, duplicate group paths, and history paths.
5. Reject `\\?\`, `\\.\`, drive-relative, ADS, UNC/share-root, alternate slash,
   trailing-dot/space, short-name, symlink, and junction escape cases.
6. Ensure `_current_workspace` matches the workspace argument for every
   operation that writes history.

#### Required tests

- Table-driven guard tests for standard, device, extended, UNC, share-root,
  short-name, case, separator, junction, and symlink forms.
- Custom rules reject `..`, absolute, drive-qualified, UNC, and device paths.
- Valid nested rule folders remain supported.
- Batch zip and duplicate APIs reject paths not produced from the selected
  workspace.
- Backup permits valid sibling destinations while rejecting self/descendant
  recursion and unsafe roots.

#### Acceptance criteria

- `custom_rule_workspace_escape` keeps the source inside the workspace and
  returns a validation error.
- `is_system_critical_dir('\\\\?\\C:\\')` or its replacement reports blocked.
- Every API method has a direct scope-validation test.

### Workstream C — Collision Safety and Transactional Batches

**Findings:** FOP-AUD-003, FOP-AUD-004, FOP-AUD-005  
**Priority:** P0

#### Implementation

1. Replace flatten’s one-level fallback with the shared collision-safe
   allocator.
2. Precompute and reserve all flatten destinations before moving anything.
3. Refactor extension changes into a preflighted two-phase rename that safely
   handles collisions, cycles, case-only changes, locked files, and failures.
4. Replace media timestamp fallbacks with unique destination allocation and
   atomic temporary-output promotion.
5. Remove partial output files after failed conversions without touching
   pre-existing files.
6. Persist batch journal entries incrementally and return partial-result details
   on interruption or failure.

#### Required tests

- Multiple existing collision levels never overwrite content.
- Two source files planning the same output receive distinct reserved names.
- Extension changes with a late collision perform no mutation or retain usable
  history for completed items.
- Swap/cycle and case-only rename cases succeed safely.
- Three consecutive conversions cannot overwrite an earlier output.
- Corrupt media input leaves no partial artifact.
- Locked/read-only file failures preserve recovery for completed items.

#### Acceptance criteria

- `flatten_collision_overwrite` preserves the sentinel content.
- `media_fallback_overwrite` preserves both pre-existing outputs and chooses a
  new destination.
- `extension_partial_failure_history` either performs zero mutations or retains
  complete recovery entries for all completed changes.

### Workstream D — Frontend/API Contract and Workspace State

**Findings:** FOP-AUD-006, FOP-AUD-009, FOP-AUD-016  
**Priority:** P0/P1

#### Implementation

1. Fix sequential rename dispatch so folder mode reaches the backend as
   `mode='folders'`.
2. Replace positional, operation-specific argument rewriting with explicit
   request objects or typed adapters.
3. Drive confirmation, dry-run, recursive, and undo behavior from the shared
   operation registry.
4. Gate every mutating operation—including media remove-original and backup—
   behind consistent preview/confirmation semantics when Simulation is off.
5. Enable Undo only when the backend confirms durable history was saved.
6. Always replace workspace-scoped state on path change:
   `customRules`, duplicates, media lists, selected files, preview data,
   archive selections, stats, and history availability.
7. Protect async workspace loads with a request/workspace token so a stale
   response cannot populate the newly selected workspace.
8. Disable repeat submissions while an operation or confirmation is active.

#### Required tests

- Rename Files and Rename Folders deliver distinct correct API payloads.
- Every operation’s confirmation/dry-run/undo behavior matches registry
  metadata.
- Batch extraction, backup, and media conversions expose Undo when durable
  history exists.
- Switching from a workspace with rules to one without rules yields `[]`.
- Delayed responses from the old workspace are ignored.
- Rapid double-clicks produce one backend mutation.

#### Acceptance criteria

- Real bridge contract tests cover every frontend operation.
- No mutating handler bypasses the unified safety gate.
- Workspace state never leaks between two disposable test workspaces.

### Workstream E — Dependency and Input Hardening

**Findings:** FOP-AUD-008, FOP-AUD-012, FOP-AUD-015  
**Priority:** P0/P1

#### Implementation

1. Remove the obsolete Pillow `<12.0` cap and pin a reviewed version at or above
   the complete fix level reported by the current advisory scan.
2. Limit enabled Pillow formats to formats the application explicitly supports.
3. Enforce image dimension/pixel/resource limits before full decode and convert
   untrusted media in a bounded worker process where practical.
4. Add archive limits for member count, expanded bytes, compression ratio,
   nesting depth, runtime, and required free space.
5. Reject archive links and special entries unless the format-specific handler
   can prove final containment.
6. Revalidate duplicates immediately before deletion using backend-held group
   IDs, canonical workspace scope, current metadata, and a strong digest or byte
   comparison.
7. Replace MD5 as the final duplicate identity or supplement it with direct byte
   verification.

#### Required tests

- Current Pillow/media regression matrix for PNG, JPEG, WebP, BMP, and corrupt
  or disguised inputs.
- Oversized dimensions and decompression bombs fail with bounded resource use.
- ZIP/TAR/7z/RAR member, ratio, size, link, and traversal corpora fail safely.
- Duplicate changed-after-scan and outside-workspace paths are rejected.
- Dependency scans show no unresolved vulnerability applicable to shipped
  functionality.

#### Acceptance criteria

- Fresh Python audit contains no unresolved High/Critical finding in shipped
  dependencies.
- Archive bombs cannot exceed configured quotas.
- Duplicate deletion never acts on stale or out-of-scope group data.

### Workstream F — Privacy and Local Content Boundary

**Findings:** FOP-AUD-010, FOP-AUD-011  
**Priority:** P0/P1

#### Implementation

1. Bundle Roboto Slab, IBM Plex Sans, and IBM Plex Mono locally with appropriate
   license notices, or use system fonts.
2. Remove Google Fonts stylesheet and preconnect links.
3. Add a restrictive Content Security Policy allowing only packaged assets and
   required local schemes.
4. Fail closed with a clear error when packaged UI assets are absent.
5. If a development server remains supported, start an app-owned server on an
   unpredictable port and authenticate/verify the expected origin before
   exposing any API. Prefer a separate development entry point with a reduced
   test API.
6. Reconcile README, privacy policy, terms, and in-app statements with verified
   behavior.

#### Required tests

- Offline launch makes zero external DNS/HTTP requests.
- Missing `ui/dist` never loads an unrelated page or exposes `OrganizerAPI`.
- CSP blocks remote scripts/styles/fonts.
- Production and development entry points have explicit, tested trust models.

#### Acceptance criteria

- Network monitoring confirms no third-party requests during startup and all
  workflows.
- The advertised offline/privacy claims match the tested binary.

### Workstream G — Locking, Deletion Reporting, and API Reliability

**Findings:** FOP-AUD-013, FOP-AUD-014  
**Priority:** P1

#### Implementation

1. Remove the duplicate `@requires_lock` decorator from
   `delete_empty_folders`.
2. Add API-level concurrency tests for every mutating method.
3. Remove permanent `shutil.rmtree` fallback when Recycle Bin support is
   unavailable; return a blocking error instead.
4. Stop swallowing media Recycle Bin exceptions. Report conversion and cleanup
   outcomes independently.
5. Distinguish success, partial success, failure, and history-not-saved states
   consistently across all API responses.

#### Required tests

- Empty-folder dry-run and live calls return without deadlock.
- Concurrent mutation attempts serialize and remain recoverable.
- Simulated Recycle Bin failure does not permanently delete and is visible in
  the UI.
- Remove-original failure reports the surviving original accurately.

#### Acceptance criteria

- `double_lock_deadlock` completes within the test timeout.
- No user-visible deletion silently falls back to permanent removal.

### Workstream H — Accessibility and Native UI Verification

**Findings:** FOP-AUD-018  
**Priority:** P1/P2

#### Implementation

1. Add explicit labels and IDs to all form controls.
2. Move focus into dialogs, trap it, make background content inert, restore
   focus on close, and support Escape where safe.
3. Verify visible focus, logical tab order, screen-reader names, switch states,
   modal announcements, and progress/status announcements.
4. Add automated axe-style checks where supported and retain manual keyboard
   checks in the release checklist.
5. Test native pywebview at 100%, 125%, 150%, and 200% Windows scaling.

#### Acceptance criteria

- No unlabeled interactive controls.
- Keyboard focus cannot leave an open modal.
- All views remain reachable and readable at minimum window size and supported
  scaling.

### Workstream I — Reproducible Packaging and Release Identity

**Findings:** FOP-AUD-017 and the known unsigned-binary limitation  
**Priority:** P1/P2, after safety fixes

#### Implementation

1. Choose a new version higher than 5.0.4; do not reuse the compromised release
   version.
2. Use one version source for Python, UI package, executable metadata, installer,
   and release tag.
3. Add Windows version resources to the portable executable, including product,
   file version, company/publisher, and source commit.
4. Pin/hash Python dependencies and PyInstaller; use `npm ci`; preserve the npm
   lockfile.
5. Upgrade Vite/esbuild to versions without the reported development-server
   advisories and retest the build.
6. Produce an SBOM, dependency-scan reports, checksums, and build provenance.
7. Sign the portable and installer with Authenticode if a certificate is
   available.
8. Tag the exact audited commit, build from a clean checkout, and compare two
   clean builds for unexplained differences.

#### Required tests

- Clean offline/controlled build from locked dependencies.
- Portable launch without Python/Node installed.
- Clean-VM installer fresh install, upgrade, reinstall, launch, and uninstall.
- Version and source commit agree across UI, file metadata, installer, SBOM,
  checksums, and tag.
- Signature and SmartScreen behavior recorded.

#### Acceptance criteria

- Both artifacts are traceable to the exact release commit.
- Installer/portable pass clean-VM testing and have published SHA-256 hashes.

## 5. Suggested Delivery Sequence

| Milestone | Scope | Findings closed | Dependency |
|---|---|---|---|
| M1 — Safety foundation | Shared path policy, operation registry, journal/undo design | Enables all later fixes | None |
| M2 — Data-loss blockers | Workstreams A–C | 001–005, 007 | M1 |
| M3 — Contract and isolation | Workstreams D and F | 006, 009–011, 016 | M1–M2 |
| M4 — Input/dependency hardening | Workstream E | 008, 012, 015 | M1 |
| M5 — Reliability and accessibility | Workstreams G–H | 013, 014, 018 | M2–M3 |
| M6 — Release engineering | Workstream I | 017 | All Critical/High fixes |
| M7 — Independent retest | Full audit rerun and clean-VM verification | All findings | M1–M6 |

M1–M4 should be treated as one release-blocking program. Accessibility and
packaging work may proceed in parallel after the shared operation/path contracts
stabilize, but no artifact should be published early.

## 6. Test and Coverage Targets

Replace the existing test-count-only gate with risk-based coverage:

- 100% of exposed `OrganizerAPI` methods have direct success, validation,
  failure, and concurrency tests as applicable.
- 100% of mutating operations have dry-run manifest comparison, collision,
  partial-failure, history, undo, and workspace-containment tests.
- 100% of deletion paths test Recycle Bin failure behavior.
- `organizer.py` line coverage target: at least 80%, with all destructive branches
  covered regardless of aggregate percentage.
- `services/media_service.py` and `services/automation_service.py` line coverage
  target: at least 85%, with hostile-input branches included.
- Frontend contract tests cover every operation button and request payload.
- Accessibility automation reports zero serious/critical violations; manual
  keyboard checks remain mandatory.
- Dependency audits report zero unresolved Critical/High issues applicable to
  shipped code.

Coverage percentages are supporting indicators. A destructive branch without a
meaningful assertion blocks release even if aggregate coverage targets pass.

## 7. Remediation Tracking Format

For each finding, record:

- Finding ID and owner.
- Fix branch/commit and affected files.
- Regression test names.
- Before/after reproduction output.
- Security and data-migration considerations.
- Reviewer and independent retest result.
- Documentation/release-note changes.
- Closure date and residual risk, if any.

Do not close a finding merely because code changed; closure requires the stated
acceptance criteria and an independent retest.

## 8. Final Release Gate

Approve a new release only when all conditions are satisfied:

- All Critical and High findings are closed and independently retested.
- Medium findings are closed or explicitly accepted with documented owner,
  rationale, mitigation, and target date.
- Every exposed API method and mutating UI workflow passes its operation
  contract tests.
- Disposable hostile-path, collision, partial-failure, archive, media, and undo
  suites pass.
- Dry-run produces byte/metadata-identical pre/post workspace manifests.
- No operation can read/write/delete outside its authorized scope through path
  spelling, traversal, link, junction, history, or stale frontend state.
- Python/npm/exact-artifact scans have no unresolved release-blocking issues.
- Production launch makes no undocumented network request.
- Native pywebview accessibility and scaling checks pass.
- Fresh portable and installer artifacts pass clean-VM smoke, upgrade, and
  uninstall tests.
- Version, commit, SBOM, checksums, signatures, tag, and release notes all refer
  to the same audited build.
- `audit/final-report.md` is rerun/replaced with a new conclusion of **Release**
  or **Release with explicitly accepted non-blocking risks**.

Until then, retain the audit conclusion: **Do not release**.
