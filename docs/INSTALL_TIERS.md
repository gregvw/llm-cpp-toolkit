# Install Method Tiers

llm-cpp-toolkit ships several install recipes at different levels of maturity.
This page classifies them so users know what to rely on and maintainers know
what to gate in CI.

These tiers reflect **current support intent and automated coverage**, not an
endorsement of one packaging system over another. Today none of the install
recipes are install-tested in CI (the release workflow *builds* some packages
but does not install or smoke-test them). Promotion to a higher tier requires a
CI job that installs the recipe and runs `llmtk --version` + `llmtk doctor`.

## Tier 1 — Supported

Primary, most-exercised paths. Expected to work; regressions here are blockers.

| Method | Command | Notes |
|--------|---------|-------|
| pipx | `pipx install llm-cpp-toolkit` | Checksummed bootstrap; standards-compatible wheel. |
| Bash installer | `curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh \| bash` | Zero-dependency installer. |
| Docker | `docker run ghcr.io/gregvw/llm-cpp-toolkit:latest` | Isolated, reproducible runtime. |

`uv` is the supported **development** workflow (`uv sync`, `uv run python -m unittest discover`, `uv build --no-sources`).

## Tier 2 — Experimental

Packaging is maintained and expected to work, but is not yet verified by CI.
Promote to Tier 1 once a CI job installs and smoke-tests it.

| Method | Command | Notes |
|--------|---------|-------|
| Nix flake | `nix develop github:gregvw/llm-cpp-toolkit` | `flake.nix` maintained; no CI install check yet. |
| Homebrew | `brew tap gregvw/llm-cpp-toolkit && brew install llmtk` | Formula present; tap not yet CI-validated. |

## Legacy / Unverified

Build recipes exist in the tree (some are produced by the release workflow) but
are not regularly installed or validated. Use at your own risk; report breakage.

| Method | Source | Notes |
|--------|--------|-------|
| Snap | `snap/` | Build script present; not install-tested. |
| Flatpak | `flatpak/` | Manifest present; not install-tested. |
| AppImage | `appimage/` | Build script present; not install-tested. |

## Roadmap

- Add CI container jobs that install each Tier 1 recipe and run `llmtk doctor`.
- Once a recipe has a passing install job, promote it (Tier 2 → Tier 1, etc.).
- Retire any Legacy recipe that cannot be revived with a maintained CI job.
