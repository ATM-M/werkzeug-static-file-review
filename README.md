# Werkzeug Static-File Security Review

A reproducible review of static-file deployment boundaries in Werkzeug. This project combines source analysis, synthetic filesystem fixtures, and regression checks to explain when backups, dotfiles, and symlinks become publicly reachable.

**Results:** 32 project tests and 21 selected upstream tests passed on Linux / WSL 2. The reviewed revision is `f7e37f0bf510fa355fdac3e922cc2078916b021f` (`3.2.0.dev`).

## What the project demonstrates

- SQL backups and dotfiles placed in an exported directory can be served without authentication in the tested configuration.
- Files and directories linked from the exported directory can make outside files reachable.
- Filename filtering has specific basename and platform-dependent matching behavior.
- Moving a backup is insufficient if an existing directory symlink still exposes its new location.
- A clean static-asset directory removes the tested exposure paths while preserving normal content.
- The tested traversal requests did not retrieve outside files.

These are bounded deployment observations. This project does not claim a newly discovered Werkzeug vulnerability, CVE, upstream acceptance, or bounty. Upstream explicitly documents that `safe_join` does not validate symlinks or filesystem properties.

## Review materials

| File | Purpose |
| --- | --- |
| [REPORT.md](REPORT.md) | Scope, source references, observations, remediation, and limitations |
| [test_audit.py](test_audit.py) | 32 local test cases using synthetic data |
| [run_checks.py](run_checks.py) | Pinned-revision checks, test execution, and evidence generation |
| [evidence/metadata.json](evidence/metadata.json) | Environment, revision, result counts, and source hashes |
| [evidence/audit.xml](evidence/audit.xml) | Individual project test results |
| [evidence/upstream-focused.xml](evidence/upstream-focused.xml) | Selected upstream test results |

## Reproduce

From this project's root directory, on Linux / WSL with Python 3.13 and Git:

```bash
git clone https://github.com/pallets/werkzeug.git upstream
git -C upstream checkout --detach f7e37f0bf510fa355fdac3e922cc2078916b021f
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_checks.py
```

Expected summaries: `32 passed` and `21 passed`. Network access is used to download source and dependencies; the tests use an in-process WSGI client and do not access external targets or open listening ports. Rerunning overwrites the generated evidence with a new execution record.

The runner verifies the upstream commit and rejects tracked upstream modifications. The focused upstream run uses `--noconftest`; it is not the full upstream test suite. Files under `upstream/` retain their upstream license and are fetched separately.

## Scope

Only synthetic files and a local checkout are tested. No production website, actual credentials, or customer data is involved. Results apply to the tested revision and environment; native Windows, reverse proxies, concurrent filesystem changes, and untested inputs require separate assessment.
