# PocoFlow — PyPI Publishing Guide

## Published Packages

| Registry | URL | Version |
|----------|-----|---------|
| **PyPI** (production) | https://pypi.org/project/pocoflow/ | 0.2.0 |
| **TestPyPI** (staging) | https://test.pypi.org/project/pocoflow/0.2.0/ | 0.2.0 |

---

## One-Time Setup

### 1. Install build tools

```bash
pip install build twine
```

### 2. Configure PyPI credentials

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-<YOUR_PYPI_API_TOKEN>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-<YOUR_TESTPYPI_API_TOKEN>
```

**Get tokens at:**
- PyPI: https://pypi.org/manage/account/token/
- TestPyPI: https://test.pypi.org/manage/account/token/

Create **project-scoped** tokens (safer than account-wide) once the project exists.

---

## Publishing a New Release

### Step 1 — Bump the version

Edit `pyproject.toml`:

```toml
[project]
version = "0.3.0"   # ← increment this
```

Also update `pocoflow/__init__.py`:

```python
__version__ = "0.3.0"
```

### Step 2 — Clean and build

```bash
cd ~/projects/digital-duck/picoflow

# Remove any previous build artefacts
rm -rf dist/ build/ *.egg-info

# Build source distribution + wheel
python -m build
```

Expected output:
```
Successfully built pocoflow-0.3.0.tar.gz and pocoflow-0.3.0-py3-none-any.whl
```

Verify the contents:
```bash
ls dist/
# pocoflow-0.3.0-py3-none-any.whl
# pocoflow-0.3.0.tar.gz

python -m twine check dist/*
# PASSED  pocoflow-0.3.0-py3-none-any.whl
# PASSED  pocoflow-0.3.0.tar.gz
```

### Step 3 — Upload to TestPyPI first

Always test on TestPyPI before touching the real PyPI index.

```bash
python -m twine upload --repository testpypi dist/*
```

Verify the install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            pocoflow==0.3.0
python -c "import pocoflow; print(pocoflow.__version__)"
```

> **Note:** `--extra-index-url pypi.org/simple/` lets pip resolve regular
> dependencies (pocketflow, dd-logging) from the real PyPI while pulling
> pocoflow itself from TestPyPI.

### Step 4 — Upload to PyPI

```bash
python -m twine upload --repository pypi dist/*
```

Verify the install from PyPI:

```bash
pip install pocoflow==0.3.0
python -c "import pocoflow; print(pocoflow.__version__)"
```

### Step 5 — Tag the release in git

```bash
cd ~/projects/digital-duck/picoflow
git tag v0.3.0
git push origin main --tags
```

---

## pyproject.toml Reference

Key fields to keep up to date on every release:

```toml
[project]
name        = "pocoflow"
version     = "0.2.0"          # bump for every release
description = "Lightweight LLM workflow orchestration — a hardened evolution of PocketFlow"
readme      = "README.md"
license     = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.10"

dependencies = [
    "pocketflow>=0.0.1",
    "dd-logging>=0.1.0",
]

[project.optional-dependencies]
ui  = ["streamlit>=1.32", "pandas>=1.5"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.urls]
Homepage   = "https://github.com/digital-duck/picoflow"
Repository = "https://github.com/digital-duck/picoflow"
```

---

## Install Variants

```bash
# Core only
pip install pocoflow

# With Streamlit monitor UI
pip install "pocoflow[ui]"

# Development (tests + UI)
pip install "pocoflow[ui,dev]"

# From TestPyPI (staging verification)
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            pocoflow

# Local editable install (for digital-duck monorepo dev)
pip install -e ~/projects/digital-duck/picoflow"[ui,dev]"
```

---

## Local Development (digital-duck monorepo)

Other projects (e.g. SPL-flow) depend on pocoflow. During dev, install from
the local checkout so changes take effect immediately without publishing:

```bash
# Install dd-logging (also local)
pip install -e ~/projects/digital-duck/dd-logging

# Install pocoflow in editable mode
pip install -e ~/projects/digital-duck/picoflow"[ui,dev]"

# Verify
python -c "import pocoflow; print(pocoflow.__version__)"
```

In SPL-flow's `requirements.txt`:
```
# Production
pocoflow>=0.2.0

# Local dev override (run this once, takes priority):
# pip install -e ~/projects/digital-duck/picoflow
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `403 Forbidden — not allowed to upload` | Project name taken by another user | Choose a different name; update `pyproject.toml` and rebuild |
| `400 File already exists` | Version already uploaded (PyPI is immutable per version) | Bump version in `pyproject.toml` and rebuild |
| `Invalid distribution` | Stale build artefacts from old package name | `rm -rf dist/ build/ *.egg-info` then rebuild |
| `HTTPError: 401 Unauthorized` | Wrong or expired API token | Regenerate token at pypi.org/manage/account/token/ |
| Setuptools deprecation warning on `license = { file = ... }` | Old TOML table format | Use `license = "MIT"` + `license-files = ["LICENSE"]` (SPDX string) |

---

## Release History

| Version | Date | Notes |
|---------|------|-------|
| 0.2.0 | 2026-02-17 | SQLite backend, dd-logging, background runner, Streamlit monitor |
| 0.1.0 | 2026-02-17 | Initial release — Store, Node, AsyncNode, Flow, hooks, JSON checkpoints |
