# Folders Organizer Pro v5.0.4 — Final Audit Report

**Audit date:** 2026-08-24  
**Audited source:** `main` at `98e29627cb3998a9f8086f9ca26f59074e2c94eb`  
**Decision:** **Do not release / withdraw Production Ready status**

## Executive Summary

The existing automated gates reproduce successfully: 33 backend tests pass,
the frontend builds cleanly, the required view-scroll layout works, and the
existing portable executable starts. Those gates do not adequately exercise
the pywebview API boundary or destructive recovery behavior. Coverage measured
only 14% for `organizer.py` and 37% overall.

The audit confirmed **1 Critical, 11 High, and 6 Medium findings**. The most
severe issue lets an editable `.organizer_history.json` instruct Undo to
permanently delete an arbitrary file or directory outside the selected
workspace. Disposable checks also proved workspace escape through custom rules,
silent flatten overwrite, media output overwrite, partial mutation without
history, and an extended Windows drive-root guard bypass.

The UI can operate on the wrong object type (“Rename Folders” dispatches file
mode), does not consistently confirm or expose Undo for mutations, and leaks
custom rules between workspaces. The current Pillow constraint resolves a
version with 25 known vulnerabilities. The stated no-network privacy guarantee
is also false because the application loads Google Fonts remotely.

## Risk Counts

| Severity | Open |
|---|---:|
| Critical | 1 |
| High | 11 |
| Medium | 6 |
| Low | 0 |

## Release Blockers

At minimum, a new release must close and retest:

1. Untrusted undo-history execution and permanent external deletion.
2. Workspace containment for all source/destination paths and custom rules.
3. Collision-safe, non-overwriting flatten/media/rename behavior.
4. Transactional or journaled recovery for partial failures.
5. Correct frontend-to-backend dispatch for folder renaming.
6. Complete system-root/namespace/junction guard coverage.
7. A safe, current Pillow version and exact-artifact dependency scan.
8. Uniform confirmation, dry-run, and Undo semantics for all mutations.
9. Removal of remote fonts or correction of privacy behavior/policy.
10. Fail-closed handling when the packaged UI is missing.
11. Archive extraction quotas and per-format hostile tests.

## Positive Results Worth Preserving

- Existing service regressions all pass.
- ZIP/TAR traversal checks cover common traversal forms.
- View roots consistently implement bounded internal scrolling.
- The minimum documented window width does not introduce page overflow.
- Theme variables and Tailwind opacity mapping are structurally sound.
- Atomic replacement is used when writing normal undo history.
- Portable and installer artifacts exist, are hashable, and the portable starts.

## Required Retest Before Release

- Add API-level tests for every exposed method, with real bridge argument
  contracts and mutation semantics.
- Add the disposable reproductions in `audit/targeted_checks.py` as regression
  tests; corrected behavior must make every vulnerable observation fail closed.
- Achieve meaningful API/media/automation coverage, prioritizing every branch
  that writes, moves, deletes, extracts, or restores files.
- Re-run Python/npm vulnerability scans against locked dependencies and inspect
  the exact frozen artifact/SBOM.
- Perform native pywebview keyboard, scaling, confirmation, progress, error,
  and recovery tests.
- Build new portable/installer artifacts from the exact tagged commit, then
  test install/upgrade/uninstall on clean snapshotted Windows VMs.
- Record hashes, version metadata, signatures, and source commit in the release.

## Audit Artifacts

- `audit/findings.md` — full finding details and remediation guidance.
- `audit/traceability-matrix.md` — documented invariant results.
- `audit/test-results.md` — passes, failures, and limitations.
- `audit/dependency-review.md` — Python/npm and build-chain review.
- `audit/evidence/baseline.md` — environment, coverage, artifact hashes, and UI evidence.
- `audit/evidence/targeted-checks-results.json` — disposable reproduction outcomes.
- `audit/targeted_checks.py` — repeatable safety reproduction harness.

