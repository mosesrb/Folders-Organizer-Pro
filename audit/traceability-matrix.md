# Audit Traceability Matrix

| Requirement / invariant | Result | Evidence or finding |
|---|---|---|
| 33 backend tests pass | PASS | Fresh isolated run: 33/33 |
| Frontend production build is clean | PASS | Fresh Vite 5.4.21 build |
| Every view has a bounded scrolling root | PASS | Static and rendered check of all ten views |
| Theme colors use raw RGB variables and `withOpacity()` | PASS with minor drift | Palette mapping verified; `.btn-primary` still embeds a literal text hex value |
| Mutating API methods are serialized | FAIL | FOP-AUD-013: `delete_empty_folders` double-locks and deadlocks |
| System-critical and bare-root operations are blocked | FAIL | FOP-AUD-007: `\\?\C:\` bypasses the guard |
| Operations stay inside the selected workspace | FAIL | FOP-AUD-002 and FOP-AUD-011 |
| Existing destination data is never overwritten | FAIL | FOP-AUD-003 and FOP-AUD-005 |
| Failed operations retain complete undo information | FAIL | FOP-AUD-004 |
| Undo history is atomic and safe | FAIL | Atomic write passes; untrusted history execution fails critically (FOP-AUD-001) |
| All deletion uses the Recycle Bin | FAIL | Undo permanently unlinks/removes; zipper has permanent-delete fallback (FOP-AUD-014) |
| Dry-run/confirmation protects all mutations | FAIL | Several mutating/media flows bypass the generic confirmation gate (FOP-AUD-009) |
| Backend media errors are surfaced | PARTIAL PASS | Tuple handling is present; output collisions and recycle failures remain unsafe |
| Archive extraction blocks traversal | PARTIAL PASS | Existing ZIP/TAR tests pass; no expansion limits and incomplete non-TAR link hardening (FOP-AUD-012) |
| App makes no remote network requests | FAIL | Google Fonts links contradict privacy promise (FOP-AUD-010) |
| Browser fallback cannot expose the bridge to untrusted content | FAIL | Localhost fallback attaches full API to whichever page owns port 5173 (FOP-AUD-011) |
| Dependencies are currently safe | FAIL | Pillow 11.3.0: 25 known vulnerabilities (FOP-AUD-008) |
| Source, tag, and artifacts identify one build | FAIL | v5.0.4 tag/HEAD/artifact metadata drift (FOP-AUD-017) |
| Portable artifact launches standalone | LIMITED PASS | Controlled 12-second process smoke test |
| Installer install/upgrade/uninstall works in clean Windows | NOT VERIFIED | Requires disposable VM/snapshot |
| Core dialogs and controls are keyboard accessible | FAIL | FOP-AUD-018 |

