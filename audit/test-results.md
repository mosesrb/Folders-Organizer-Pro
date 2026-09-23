# Audit Test Results

## Passed

- Backend baseline: 33/33 existing tests.
- Frontend: production Vite build completed successfully.
- Current ZIP/TAR traversal regression tests passed.
- Existing system-directory test cases passed for standard path spellings.
- Every rendered workspace view used the required bounded scrolling root.
- Advanced and Media views scrolled internally at the tested viewport.
- Minimum documented 1180×780 layout had no page-level horizontal overflow.
- Tailwind palette uses raw RGB variables through `withOpacity()`.
- Existing portable executable remained running during a 12-second smoke launch.

## Failed

- 7/7 targeted safety checks reproduced a defect or guard gap:
  - API double-lock deadlock.
  - Untrusted history deleted outside its workspace.
  - Custom rule moved a file outside its workspace.
  - Flatten overwrote a pre-existing collision.
  - Media fallback overwrote a pre-existing output.
  - Extension batch partially mutated then lost its history.
  - Extended drive-root form bypassed the critical-directory guard.
- “Rename Folders” bridge dispatch statically resolves to file mode.
- API/service coverage is insufficient: 14% for `organizer.py`, 37% overall.
- Python dependency audit found 25 known Pillow vulnerabilities.
- Frontend dependency audit found one High and one Moderate package-level
  advisory (Vite/esbuild chain; development/build exposure).
- Remote Google Fonts links contradict offline/no-network claims.
- Modal focus containment/Escape behavior failed.
- Twelve rendered form controls lacked programmatic labels.
- Source/tag/artifact versions and metadata do not identify one exact build.

## Not Fully Verified

- Installer fresh install, upgrade, uninstall, and leftovers on clean Windows.
- RAR extraction requiring an external WinRAR/7-Zip executable.
- Hostile RAR/7z link entries and archive-bomb behavior.
- Windows scaling at 125%, 150%, and 200% inside the native pywebview window.
- Full manual operation matrix in the published portable binary.
- Antivirus/SmartScreen behavior beyond confirming both artifacts are unsigned.
- Reproducible two-build comparison.

These limitations do not soften the release result: confirmed Critical/High
findings already fail the release gate.

