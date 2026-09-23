# Dependency Review

## Python

`requirements.txt` uses broad lower bounds and caps Pillow below 12:

```text
pywebview>=4.4
send2trash>=1.8
py7zr>=0.20
rarfile>=4.1
Pillow>=10.0,<12.0
pypdf>=4.0
miniaudio>=1.59
```

Resolving these constraints on 2026-08-24 installed Pillow 11.3.0. A fresh
`pip-audit` found **25 known vulnerabilities in Pillow** and none in the other
resolved Python packages. The reported issues include memory corruption,
out-of-bounds reads/writes, information disclosure, command injection in a
Pillow viewer path, and multiple denial-of-service conditions. Several are
fixed only in Pillow 12.2.0 or 12.3.0, which the repository's `<12.0` cap
forbids.

This is relevant to the product because it opens and re-encodes files selected
from user workspaces. Pillow identifies formats by content, so a hostile file
does not become safe merely because it has an expected extension.

Recommended action: remove the obsolete upper bound after compatibility tests,
pin a reviewed Pillow release at or above the complete fix level, constrain
accepted formats and resource use, then rebuild and rescan the binaries.

## Frontend

An npm audit of the checked-in lockfile reported:

- 1 High advisory affecting Vite (`server.fs.deny` bypass on Windows alternate
  paths), plus two moderate Vite advisories.
- 1 Moderate advisory affecting esbuild, transitively through Vite.

These packages are build/dev-server dependencies and are not shipped as a Node
runtime in the desktop executable. They still matter because the documented
development workflow runs Vite and `organizer.py` falls back to port 5173 when
the compiled UI is absent.

## Reproducibility and Supply Chain

- Python runtime dependencies are not fully pinned and have no hash-locked
  requirements file.
- PyInstaller is installed on demand without a pinned version.
- `setup.bat` uses `npm install`, not the lockfile-enforcing `npm ci`.
- No SBOM or dependency manifest is emitted with release artifacts.
- Neither executable is Authenticode signed.

Recommended action: adopt pinned, hashed Python lockfiles; use `npm ci`; pin
build tooling; generate an SBOM and checksums; scan the exact frozen artifact;
and sign the final binaries after all release blockers are closed.

