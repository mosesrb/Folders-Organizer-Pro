# Audit Baseline Evidence

**Captured:** 2026-08-24 (Asia/Calcutta)  
**Branch:** `main`  
**Commit:** `98e29627cb3998a9f8086f9ca26f59074e2c94eb`  
**Remote release tag:** `v5.0.4` → `c48e3a3ea75d10a4c644b6601bc93fe6c2068002`  
**Initial working tree:** clean except for the newly requested audit-plan file  
**Audit Python:** 3.12.13 in an isolated temporary virtual environment  
**Node used for build:** 24.19.0 through the bundled workspace runtime  
**Vite:** 5.4.21

The default workstation `python` and `npm` launchers were broken. This was
treated as an environment issue; the audit used isolated/bundled runtimes.

## Quality Gates

| Gate | Result | Evidence |
|---|---|---|
| Backend unit tests | PASS | 33/33 tests passed in 0.965 seconds after declared dependencies were installed |
| Frontend production build | PASS | 1,483 modules transformed; build completed in 26.62 seconds with no build errors |
| Existing-test coverage | WEAK | `organizer.py` 14%, services mixed 18–80%, overall 37% |
| Portable smoke launch | PASS (limited) | Existing portable process remained alive for a controlled 12-second hidden launch |
| Installer execution | NOT RUN | No disposable Windows VM/snapshot was available; live execution could alter an existing installation sharing the same Inno `AppId` |

Coverage command scoped to `organizer,services`:

```text
Name                             Cover
organizer.py                       14%
services/automation_service.py     48%
services/duplicate_service.py      80%
services/file_service.py           60%
services/media_service.py          18%
services/organizer_service.py      71%
TOTAL                              37%
```

The low API-bridge coverage explains why all 33 service-oriented tests pass
while bridge-level dispatch, locking, undo, and media defects remain.

## Distribution Artifacts

| Artifact | Bytes | SHA-256 | Signature | Version metadata |
|---|---:|---|---|---|
| `FoldersOrganizerPro_Portable.exe` | 119,247,066 | `F9FFC741595A0BB1A81334763331C92E6E969102106CEB806CE0E60F233F6E50` | Not signed | Missing file/product/company metadata |
| `FoldersOrganizerPro_Setup.exe` | 120,350,247 | `E62C6646241335AD1535F15DEC4F2410166DD3685A10B38CD1BCA8E2265C9036` | Not signed | Product version 5.0.4, publisher Moses RB |

The artifacts were built before commit `98e2962` added the first-run privacy
and terms UI, yet the source and artifacts all identify as 5.0.4. The remote
v5.0.4 tag points to the earlier `c48e3a3` commit.

## Rendered UI Checks

- All ten workspace views retained the required
  `absolute inset-0 overflow-y-auto custom-scrollbar` root.
- At 1180×780, Advanced Tools had no page-level horizontal overflow and its
  internal root remained vertically scrollable.
- Media Tools and Advanced Tools correctly exposed internal scrolling when
  content exceeded the viewport.
- The terms/privacy dialog did not move focus into the dialog; focus remained
  on its background opener. Escape did not close the dialog.
- Twelve text/number controls across Renamer, Extension Changer, Advanced
  Tools, and Custom Rules lacked a programmatic label.
- Rendered HTML contained live external Google Fonts preconnect and stylesheet
  links despite the in-app and repository claims of no network calls.

