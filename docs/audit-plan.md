# Folders Organizer Pro — Application Audit Plan

**Prepared:** 2026-08-24  
**Audit targets:** source application, portable executable, and Windows installer  
**Baseline described by project docs:** v5.0.4, published 2026-08-20

## 1. Purpose

Independently verify that Folders Organizer Pro is safe, correct, usable, and
release-ready across its Python services, pywebview API bridge, React UI,
portable executable, and installer.

The existing statements that the application is “Production Ready,” that all
33 backend tests pass, and that the frontend build is clean are inputs to the
audit, not substitutes for fresh audit evidence.

## 2. Source Documents

The audit is based on these repository documents:

- `docs/architecture.md` — system structure, UI layout, design system, and
  build/run behavior.
- `docs/memories.md` — durable safety, concurrency, theming, packaging, and
  layout invariants.
- `docs/project-status.md` — current quality claims, release artifacts,
  roadmap, and known code-signing limitation.
- `docs/worklogs.md` — prior defects, regression areas, and release history.

Where documentation and implementation disagree, record a finding and treat
the implementation as unverified until the discrepancy is resolved.

## 3. Audit Principles and Safety Controls

- Perform destructive-operation tests only inside disposable temporary
  workspaces populated with generated fixtures. Never use real user folders.
- Take a VM snapshot before installer, uninstall, system-directory, archive,
  file-locking, or malformed-input tests.
- Exercise every mutating workflow in dry-run mode first, verify that no file
  metadata or content changed, then repeat against a disposable fixture with
  dry-run disabled.
- Hash fixture files before and after each test so unexpected mutation or data
  loss is detectable.
- Test deletion workflows by confirming items reach the Windows Recycle Bin;
  do not accept permanent deletion as correct behavior.
- Preserve commands, logs, screenshots, hashes, versions, and fixture details
  as evidence. A pass without reproducible evidence is not considered closed.
- Do not publish, upload, sign, or replace release artifacts during the audit.

## 4. Finding Severity

| Severity | Definition | Release effect |
|---|---|---|
| Critical | Data loss, arbitrary file write/extraction, system compromise, or guard bypass with broad impact | Immediate stop; release blocked |
| High | Destructive action without effective confirmation/dry-run/undo, critical-directory access, corrupted output, or installer failure | Release blocked |
| Medium | Incorrect result with a safe workaround, important accessibility/usability defect, incomplete error reporting, or meaningful documentation drift | Fix or explicitly accept before release |
| Low | Cosmetic, minor consistency, maintainability, or low-impact documentation issue | Track; does not normally block release |

Each finding must include an ID, severity, affected version/component,
preconditions, exact reproduction steps, expected and actual behavior,
evidence, user impact, suspected cause, and recommended remediation. Retests
must link back to the original finding.

## 5. Audit Phases

### Phase 0 — Baseline and Traceability

1. Record the commit, branch, working-tree state, Python/Node/npm versions,
   Windows build, WebView2 runtime, and dependency versions.
2. Inventory all exposed `OrganizerAPI` methods and map each frontend call to
   its backend method, service implementation, destructive potential, guard,
   dry-run behavior, confirmation behavior, undo behavior, and existing test.
3. Inventory the portable and installer artifacts. Record filenames, sizes,
   SHA-256 hashes, version metadata, signatures, and build provenance.
4. Build a requirements traceability matrix from the invariants in
   `architecture.md` and `memories.md`.
5. Note stale or inconsistent version claims, including the UI package version
   versus the documented application/release version.

**Exit:** every user-visible operation and release artifact has an audit row,
an owner, and a planned verification method.

### Phase 1 — Reproduce Existing Quality Gates

Run from a clean checkout with pinned/reproducible dependencies where
possible:

```powershell
python -m unittest tests.test_services
Set-Location ui
npm run build
```

Also run a clean frontend dependency installation using the lockfile, scan the
test output for skipped tests and warnings, and compare actual test counts and
build output with `docs/project-status.md`.

Coverage is not currently an established gate. Measure Python service/API
coverage during the audit and identify untested destructive branches rather
than declaring a pass solely from the existing 33 tests.

**Exit:** the documented baseline is either reproduced with retained logs or a
finding explains the variance.

### Phase 2 — Static Architecture, Safety, and Security Review

Review `organizer.py` and every module under `services/` for the following:

#### API boundary and concurrency

- Every frontend API call resolves to a real backend method with compatible
  arguments and a consistently handled response shape.
- Every mutating API method is protected by `@requires_lock`.
- Simultaneous requests cannot interleave writes, corrupt history, or leave the
  UI in a false completed state.
- Inputs are validated at the API boundary, including empty strings, malformed
  regexes, invalid extensions, out-of-range quality/threshold values, missing
  paths, and path type mismatches.
- Backend exceptions are converted into useful UI-visible errors without
  leaking sensitive system details unnecessarily.

#### Filesystem safety

- Every directory operation applies the system-critical-directory guard,
  including alternate slashes, casing, trailing separators, `..`, symlinks or
  junctions, UNC paths, extended-length paths, and bare drive roots.
- Guard checks are performed against canonical/resolved targets and cannot be
  defeated by a child path that resolves into a protected location.
- All deletions use `send2trash`; search explicitly for permanent-delete calls
  such as `os.remove`, `Path.unlink`, and `shutil.rmtree`, then justify or flag
  every occurrence.
- Name collisions, case-only renames, locked files, read-only files, long
  paths, non-ASCII names, and interrupted operations fail safely.
- Undo history is written atomically, scoped to the correct workspace, and
  cannot move files outside the intended workspace when replayed.
- Dry-run paths do not write data, metadata, history, archives, output folders,
  rules, or temporary files.

#### Archive and media safety

- ZIP, TAR, 7z, and RAR extraction rejects absolute paths, traversal, mixed
  separators, drive-qualified members, links escaping the output directory,
  duplicate/conflicting members, and archive bombs or unreasonable expansion.
- Partial extraction/conversion failures are reported and do not appear as a
  success.
- Every media service `(destination, error)` tuple is checked correctly by
  single-file and batch callers.
- “Remove original” happens only after a valid destination is fully written
  and verified.

#### Dependency, privacy, and local attack surface

- Review Python and npm dependencies for known vulnerabilities, unsupported
  versions, unnecessary packages, and reproducibility risks.
- Confirm the app opens no network listener and performs no undocumented
  telemetry or upload.
- Confirm privacy/terms statements match actual file access, history storage,
  and network behavior.
- Review pywebview configuration and loaded content so untrusted remote pages
  cannot gain access to the Python bridge.

**Exit:** all critical invariants have code references and either pass evidence
or a filed finding.

### Phase 3 — Automated Functional and Regression Testing

Expand tests around a generated fixture matrix containing nested folders,
duplicates, empty folders, non-ASCII names, long names, mixed-case extensions,
zero-byte and large sparse files, locked/read-only files, collisions, images,
MP3s, PDFs, and safe/malicious archives.

Verify each operation in dry-run and live modes where applicable:

| Area | Required checks |
|---|---|
| Workspace analysis | Counts, byte totals, categories, largest files, inaccessible entries, empty workspace |
| Rename | Sequential, prefix/suffix, regex deletion, empty/invalid regex, filters, recursive toggle, collision and rollback behavior |
| Organize | Flatten, date sort, smart category priority, existing destination names, locked files |
| Duplicates | Content-based grouping, partial/full hash behavior, oldest/newest/shallowest selection, deterministic results, recycle-bin deletion |
| Automation | Old-file cleanup, recursive empty-folder pruning, archive-large-files, additive backup self-nesting and repeat runs |
| Archives | Batch zip custom extension, collision handling, delete-original-after-success, all supported extract formats, traversal corpus |
| Media | MP3→WAV, PDF compression, image optimization/format conversion, invalid/corrupt inputs, remove-original sequencing |
| State | Undo after every supported mutation, restart and reload history, corrupt history file, cross-workspace switching |
| Concurrency | Two mutations at once, analysis during mutation, cancellation/window close during work |

For each dry-run test, compare a recursive pre/post manifest containing path,
size, timestamp, attributes, and SHA-256 hash. The manifests must be identical.

**Exit:** all supported operations have success, failure, edge-case, and
dry-run coverage; no unresolved Critical or High result remains.

### Phase 4 — Frontend, Bridge, and UX Audit

Test the React UI both in browser fallback mode and inside pywebview.

- Exercise every navigation view, control, modal, status message, progress
  update, empty state, and error state.
- Confirm every `renderWorkspace()` root retains
  `absolute inset-0 overflow-y-auto custom-scrollbar` and that all content is
  reachable at the documented default and minimum window sizes.
- Verify the system-critical warning, destructive confirmation, simulation
  preview, loading overlay, undo control, and status rail against real backend
  responses—not only browser mocks.
- Ensure double clicks and repeated submissions cannot start duplicate
  destructive operations.
- Check keyboard-only use, visible focus, tab order, modal focus trapping,
  Escape behavior, accessible names, semantic labels, color contrast, reduced
  motion, and 100%/125%/150%/200% Windows scaling.
- Test light/dark/system themes, persistence, pre-paint behavior, and Tailwind
  opacity modifiers. Verify all CSS color variables are raw RGB triplets and
  every Tailwind color uses `withOpacity()`.
- Confirm button text uses the documented contrast tokens and that the flat
  “Filing Cabinet” visual language remains consistent.
- Compare browser-mock responses with real bridge response contracts so the
  dev UI cannot conceal integration defects.

**Exit:** every view is operable at minimum supported dimensions and scaling;
all destructive workflows clearly communicate scope, preview, result, and
recovery.

### Phase 5 — Portable Executable and Installer Audit

Build fresh artifacts from the audited commit, then test them on clean Windows
VMs rather than relying only on previously published binaries.

#### Portable executable

- Launch without an installed Python or Node runtime.
- Verify UI, icon, WebView2 handling, all bundled media/archive dependencies,
  frozen asset resolution via `sys._MEIPASS`, and paths containing spaces or
  non-ASCII characters.
- Test from a user-writable directory, a read-only directory, a long path, and
  a standard downloaded-file context.
- Verify single-instance/concurrent-launch behavior and clean shutdown.

#### Installer and uninstaller

- Validate publisher/version/product metadata, install location, Start Menu and
  optional desktop shortcuts, Add/Remove Programs entry, upgrade/reinstall
  behavior, per-user/admin prompts, repair behavior if applicable, and launch.
- Uninstall and inventory leftovers. User data/history must not be silently
  destroyed, while installed application files and shortcuts must be removed.
- Check both fresh install and upgrade from the prior published release.
- Record SmartScreen/antivirus behavior. The documented unsigned-binary warning
  is an accepted known limitation only if no stronger security issue appears;
  code signing remains a release-hardening recommendation.

#### Artifact integrity

- Compare source version, UI version, executable metadata, installer metadata,
  filenames, and release tag.
- Generate SHA-256 checksums and a software/dependency inventory.
- Compare two clean builds to identify reproducibility differences and explain
  expected timestamp/signing variance.

**Exit:** both distribution forms install or launch cleanly on supported
Windows environments and are traceable to the audited commit.

### Phase 6 — Documentation and Release Readiness

- Verify README, privacy, terms, architecture, build instructions, dependency
  prerequisites, RAR limitations, release notes, and screenshots against the
  audited behavior.
- Reconcile duplicated or stale architectural claims, including class naming,
  hashing algorithm descriptions, supported Python version, artifact sizes,
  and current test count.
- Confirm recovery guidance explains simulation, confirmation, Recycle Bin,
  undo limitations, and backup recommendations without overstating safety.
- Re-run all blocking tests after fixes and conduct targeted regression tests
  for every finding.

**Exit:** documentation and release metadata describe the tested application,
not an earlier implementation.

## 6. Recommended Execution Order

1. Baseline and traceability matrix.
2. Existing unit tests and clean frontend build.
3. Static safety/security review.
4. Automated fixture-based functional tests.
5. pywebview UI and accessibility tests.
6. Fresh portable/installer builds and clean-VM tests.
7. Documentation reconciliation, remediation retests, and final report.

Security and data-loss findings take precedence over visual polish. Stop the
affected destructive test area immediately if a fixture escapes its workspace,
the critical-directory guard fails, or dry-run causes a write.

## 7. Deliverables

- `audit/traceability-matrix.md` — requirement/API/operation-to-test mapping.
- `audit/evidence/` — version captures, command logs, screenshots, hashes, and
  fixture manifests (excluding secrets and large binaries).
- `audit/findings.md` — open and closed findings with severity and retest state.
- `audit/test-results.md` — automated, manual, UI, portable, and installer
  results by environment.
- `audit/dependency-review.md` — Python/npm inventory and vulnerability review.
- `audit/final-report.md` — executive summary, residual risk, known
  limitations, and release recommendation.

## 8. Final Release Gate

Recommend release only when all of the following are true:

- No open Critical or High findings.
- Every destructive operation has verified confirmation, dry-run integrity,
  failure safety, and recovery behavior.
- Critical-directory, archive traversal, Recycle Bin, atomic history, and
  concurrency invariants have direct test evidence.
- Backend tests and the production frontend build pass from a clean checkout.
- Every user-visible operation passes the source/pywebview integration audit.
- Fresh portable and installer artifacts pass clean-VM smoke and upgrade tests.
- Artifact versions and hashes are recorded and traceable to the audited
  commit.
- Medium findings are fixed or explicitly accepted with an owner and target
  date; Low findings are logged.
- Documentation accurately describes verified behavior and remaining risks.

Possible conclusions are **Release**, **Release with documented accepted
risks**, or **Do not release**. The conclusion must cite evidence and unresolved
findings rather than rely on the prior project-status label.
