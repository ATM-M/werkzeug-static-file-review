"""Run this review and a focused upstream baseline, and record provenance."""

import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "upstream"
COMMIT = "f7e37f0bf510fa355fdac3e922cc2078916b021f"


def git(*args):
    return subprocess.check_output(
        ["git", "-C", str(UPSTREAM), *args], text=True
    ).strip()


def main():
    if git("rev-parse", "HEAD") != COMMIT:
        raise SystemExit("Upstream commit does not match the reviewed revision.")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("Tracked upstream source has been modified.")
    # Use only the checked-out source, not an unrelated installed Werkzeug.
    os.environ["PYTHONPATH"] = str(UPSTREAM / "src")
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    suites = {
        "audit": ["test_audit.py"],
        "upstream-focused": [
            "upstream/tests/test_security.py",
            "upstream/tests/middleware/test_shared_data.py",
        ],
    }
    results = {}
    for name, paths in suites.items():
        command = [
            sys.executable, "-m", "pytest", "--noconftest", "-q",
            "-p", "no:cacheprovider", "-o", "addopts=",
            f"--junitxml={evidence / (name + '.xml')}", *paths,
        ]
        result = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False,
        )
        print(f"[{name}]\n{result.stdout}", end="")
        evidence.joinpath(name + ".txt").write_text(result.stdout, encoding="utf-8")
        xml_path = evidence / (name + ".xml")
        counts = {}
        if xml_path.exists():
            suites_xml = ET.parse(xml_path).getroot().findall("testsuite")
            counts = {
                key: sum(int(suite.get(key, 0)) for suite in suites_xml)
                for key in ("tests", "failures", "errors", "skipped")
            }
        results[name] = {"exit_code": result.returncode, **counts}

    source_files = [
        UPSTREAM / "src/werkzeug/security.py",
        UPSTREAM / "src/werkzeug/middleware/shared_data.py",
        ROOT / "test_audit.py",
        ROOT / "run_checks.py",
    ]
    metadata = {
        "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "repository": "https://github.com/pallets/werkzeug",
        "commit": COMMIT,
        "upstream_version_label": "3.2.0.dev",
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("MarkupSafe", "pytest", "iniconfig", "packaging", "pluggy", "Pygments")
        },
        "method": "In-process WSGI tests on synthetic temporary files; no network targets",
        "suites": results,
        "sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "claim": "Bounded deployment-behavior review; no new vulnerability or CVE claimed.",
    }
    evidence.joinpath("metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return int(any(result["exit_code"] for result in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
