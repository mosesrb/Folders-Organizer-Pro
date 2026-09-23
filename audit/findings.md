# Audit Findings — v5.0.4 / `98e2962`

All findings are open. Reproductions used disposable fixtures only. The audit
did not change application behavior.

## FOP-AUD-001 — Critical — Editable undo history can permanently delete arbitrary paths

**Affected:** `organizer.py:86-103`, `organizer.py:162-224`

`.organizer_history.json` is loaded as trusted executable instructions. An
entry with `action: "create"` and an arbitrary `dst` causes Undo to recursively
delete that directory with `shutil.rmtree`; `action: "copy"` permanently
unlinks an arbitrary file. There is no schema validation, workspace containment
check, ownership token, integrity check, critical-directory guard, or Recycle
Bin protection. The UI enables Undo merely because the editable file is
non-empty and does not put Undo behind the destructive confirmation gate.

**Reproduction:** a disposable workspace history pointed `dst` at a sibling
fixture directory. `undo_last_operation()` reported success and permanently
deleted the sibling and its sentinel file.

**Impact:** selecting an untrusted workspace and pressing Undo can destroy data
outside that workspace, potentially including large user directories.

**Recommendation:** validate a strict history schema; cryptographically bind or
internally store history; canonicalize every path; require every target to be a
known output created by the recorded operation and remain inside approved
roots; use the Recycle Bin; confirm destructive undo; reject unknown actions;
and never clear failed history until recovery is resolved.

## FOP-AUD-002 — High — Custom rule folders can escape the workspace

**Affected:** `ui/src/App.jsx:104-106`, `ui/src/App.jsx:1181-1185`,
`services/organizer_service.py:174-224`

The rule editor accepts an arbitrary folder string. The service joins it to the
workspace without rejecting absolute paths or `..`. A rule folder of
`../escaped` moved a matching file into a sibling directory and reported
success.

**Impact:** a typo or crafted rule can move files outside the directory the user
approved, including into unrelated writable locations.

**Recommendation:** normalize rule destinations, reject absolute/drive/UNC and
parent traversal forms, verify the resolved target remains under the workspace,
and apply the critical-directory guard to final destinations.

## FOP-AUD-003 — High — Flatten silently overwrites an existing second-collision file

**Affected:** `services/organizer_service.py:136-143`

Flatten checks the first destination once and then uses `_<index>` without
checking that the fallback is free. On Windows, `shutil.move` overwrote that
existing fallback. A sentinel `beta_1.txt` was replaced by the nested
`beta.txt`, while the API reported “Successfully flattened 2 files.”

**Impact:** irreversible loss of pre-existing file content.

**Recommendation:** use the shared collision-safe destination helper for every
file, reserve planned names before moving, and add a regression test with two
pre-existing collision levels.

## FOP-AUD-004 — High — Partial extension changes are not retained in undo history

**Affected:** `organizer.py:308-345`

The operation renames files one by one but only assigns/saves history after the
entire loop. With `a.old`, `b.old`, and an existing `b.new`, `a.old` became
`a.new`; the second rename failed; the API reported failure; and no history
entry or history file was retained for the completed first mutation.

**Impact:** a failed batch can leave the workspace partially changed with no
application recovery path.

**Recommendation:** preflight all destinations and locks before mutation, use a
two-phase collision-safe rename plan, persist incremental journal entries, and
return partial-success details without discarding recovery state.

## FOP-AUD-005 — High — Media fallback names can overwrite existing outputs

**Affected:** `services/media_service.py:11-28`, `35-55`, `62-77`

Each media function checks the primary output once, then falls back to a name
derived from the source modification timestamp without checking that fallback.
The image reproduction pre-created both names; optimization overwrote the
fallback sentinel and reported success. MP3 and PDF code use the same pattern.

**Impact:** pre-existing generated or user-created files matching the fallback
pattern can be destroyed.

**Recommendation:** use an atomic, collision-safe allocator; write to a unique
temporary file; validate output; and atomically rename only to a confirmed-free
destination.

## FOP-AUD-006 — High — “Rename Folders” dispatches file mode

**Affected:** `ui/src/App.jsx:430-434`, `ui/src/App.jsx:797-798`

The button calls `runOperation('sequential_rename', prefix, 'folders')`, but
`executeOperation` discards those arguments and always builds
`[prefix, 'files', ...]` for `sequential_rename`.

**Impact:** a user asking to rename folders can instead rename files, with no
generic confirmation when Simulation is off.

**Recommendation:** preserve the requested mode in a typed operation contract
and add frontend-to-API contract tests for both buttons.

## FOP-AUD-007 — High — Extended Windows drive root bypasses the critical-directory guard

**Affected:** `organizer.py:23-49`

`is_system_critical_dir('\\\\?\\C:\\')` returned `False`. The bare-root test
only blocks anchors whose string length is at most three, excluding the Windows
extended namespace form.

**Impact:** direct bridge calls can invoke destructive operations against a
drive root through an alternate Windows path spelling.

**Recommendation:** canonicalize Windows namespace/UNC/device paths using
Windows APIs, explicitly reject all volume/share roots, resolve junctions, and
test standard, extended, device, short-name, UNC, trailing-dot, and alternate
separator representations at the API boundary and for final destinations.

## FOP-AUD-008 — High — Pillow constraint forces a release with known vulnerable image processing

**Affected:** `requirements.txt:5`, packaged media/image workflows

The current constraint resolves Pillow 11.3.0 and forbids Pillow 12.x. A fresh
audit reported 25 known vulnerabilities in that package, with complete fixes
requiring later 12.x releases. The application processes files from user
workspaces using Pillow.

**Impact:** crafted inputs may cause process crashes, memory exhaustion,
information disclosure, memory corruption, or other dependency-specific
effects.

**Recommendation:** update and pin Pillow at a fully fixed version, constrain
formats/resources, rebuild, scan the exact frozen artifact, and regression-test
supported image operations.

## FOP-AUD-009 — High — Confirmation and recovery coverage is incomplete

**Affected:** `ui/src/App.jsx:319-396`, `402-417`, `430-515`

The generic confirmation list omits several mutating operations, including
sequential rename, date sort, smart categorize, image conversion, additive
backup, empty-folder deletion, and media operations that can remove originals.
The undo-enabled list omits additive backup and batch extraction, while media
handlers do not enable Undo after the backend creates history.

**Impact:** material filesystem changes may execute immediately when Simulation
is off, and users may be unable to reach the advertised recovery action.

**Recommendation:** derive confirmation, preview, undo, and destructive
semantics from one backend operation registry; require preview/confirmation for
all mutations; and test each UI action through the real bridge.

## FOP-AUD-010 — High — “No network requests” privacy promise is false

**Affected:** `ui/index.html:20-22`, `PRIVACY.md`, `README.md`, in-app privacy dialog

The UI preconnects to Google and loads three font families from
`fonts.googleapis.com`/`fonts.gstatic.com`. The privacy policy promises no
remote requests and no transmission of IP address or device information; the
in-app dialog repeats that there are no network calls.

**Impact:** launching the app can contact a third party and disclose normal
connection metadata, contradicting a core privacy guarantee.

**Recommendation:** bundle fonts locally and remove all remote links, or rewrite
the policy and obtain an appropriate user choice before any third-party request.
For the advertised product, local bundling is the consistent fix.

## FOP-AUD-011 — High — Dev fallback exposes the full file API to whichever page owns localhost:5173

**Affected:** `organizer.py:857-870`

If `ui/dist/index.html` is missing, the app loads `http://localhost:5173` and
still attaches the full `OrganizerAPI`. It does not verify that the expected
Vite app owns the port or authenticate the page.

**Impact:** an unexpected local page on that port can receive a powerful
filesystem bridge when the app is launched from an incomplete source tree.

**Recommendation:** fail closed when bundled assets are missing, or launch and
authenticate an app-owned server on an unpredictable port with strict origin
checks and a least-privilege API.

## FOP-AUD-012 — High — Archive extraction has no expansion/resource limits

**Affected:** `services/automation_service.py:186-348`

Member-path checks exist for supported formats and the current ZIP/TAR traversal
tests pass. However, extraction has no member-count, expanded-byte, compression-
ratio, depth, time, or free-space limit. 7z/RAR validation also does not inspect
link targets with the same explicit logic used for TAR.

**Impact:** a small archive can exhaust disk/memory or hang the application; a
format-specific link feature may escape the intended extraction policy.

**Recommendation:** preflight and stream against explicit quotas, reject links
and special entries unless safely supported, enforce final-path containment at
write time, and add hostile corpora for every supported format.

## FOP-AUD-013 — Medium — Empty-folder API deadlocks

**Affected:** `organizer.py:436-438`

`delete_empty_folders` is decorated with `@requires_lock` twice. Because the
lock is a non-reentrant `threading.Lock`, a disposable dry-run did not complete
within one second and never reached the service.

**Impact:** the exposed API hangs indefinitely. The current UI has no visible
button for it, reducing present user reachability but leaving the bridge method
broken.

**Recommendation:** remove the duplicate decorator and add API-level timeout
and bridge tests.

## FOP-AUD-014 — Medium — Deletion guarantees have permanent and silent-failure exceptions

**Affected:** `organizer.py:197-212`, `organizer.py:682-688`, `716-721`,
`743-748`, `777-782`, `804-809`, `838-843`,
`services/automation_service.py:510-515`

Undo permanently deletes generated files/directories, batch zipper permanently
uses `shutil.rmtree` if `send2trash` is unavailable, and media remove-original
handlers swallow all Recycle Bin errors while still reporting conversion
success.

**Impact:** behavior contradicts the documented Recycle Bin invariant and can
either permanently delete data or falsely imply requested cleanup occurred.

**Recommendation:** fail closed if Recycle Bin support is unavailable, report
deletion failures, and make undo deletion safe and identity-checked.

## FOP-AUD-015 — Medium — Duplicate deletion does not revalidate content, scope, or group provenance

**Affected:** `organizer.py:272-284`, `services/duplicate_service.py:106-128`

Deletion trusts file paths round-tripped from the UI. It neither confirms that
paths remain under the selected workspace nor rehashes immediately before
deletion. MD5 is used as the final content identity. A file changed after scan
can therefore be trashed as though it were still a duplicate.

**Impact:** stale or manipulated groups can move unique or out-of-scope files to
the Recycle Bin.

**Recommendation:** issue opaque backend group IDs, keep scan state server-side,
canonicalize scope, re-stat and compare a strong digest/byte content immediately
before deletion, and reject changed groups.

## FOP-AUD-016 — Medium — Empty rule sets leak rules across workspaces

**Affected:** `ui/src/App.jsx:188-195`

`loadRules` only calls `setCustomRules` when the new workspace returns a
non-empty list. Switching from a workspace with rules to one with no rules
leaves the first workspace's rules active.

**Impact:** Smart Sort can organize a new workspace using rules belonging to a
previous workspace.

**Recommendation:** always set `customRules` to `res.rules || []`, clear scoped
state immediately on path change, and protect against stale async responses.

## FOP-AUD-017 — Medium — Build and release identity is not traceable to one version

**Affected:** `ui/package.json`, `FoldersOrganizerPro.spec`, build scripts,
release artifacts and tag

The Python app and installer report 5.0.4 while `ui/package.json` reports 4.0.0.
The portable has no Windows version metadata. HEAD contains later application
changes but still reports 5.0.4, and the remote v5.0.4 tag points to an earlier
commit. Dependencies and PyInstaller are not fully pinned; setup uses
`npm install`. Both binaries are unsigned.

**Impact:** users and auditors cannot reliably determine which source produced
an artifact, and clean builds are not reproducible.

**Recommendation:** use a single version source, embed commit/version metadata,
tag the exact audited commit, pin/hash dependencies and build tools, use
lockfile-enforcing installs, emit SBOM/checksums, and sign final binaries.

## FOP-AUD-018 — Medium — Dialog focus and form labeling are incomplete

**Affected:** multiple controls and dialogs in `ui/src/App.jsx`

Rendered testing found twelve inputs without programmatic labels. Opening the
terms/privacy dialog left keyboard focus on the background opener; focus was
not trapped, and Escape did not close it.

**Impact:** keyboard and screen-reader users can lose context or be unable to
identify fields reliably.

**Recommendation:** add explicit labels/IDs, move focus into dialogs, trap and
restore focus, support Escape where safe, make background content inert, and
add automated accessibility checks plus keyboard tests.

