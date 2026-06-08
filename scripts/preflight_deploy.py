from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "Dockerfile",
    ".dockerignore",
    "render.yaml",
    "app/main.py",
    "app/storage.py",
    "frontend/src/main.jsx",
    "frontend/src/styles.css",
    "scripts/verify_feishu_deploy.py",
    "docs/feishu-deploy.md",
    "docs/feishu-release-handoff.md",
    "docs/page-spec.md",
    "tests/test_verify_feishu_deploy.py",
]
REQUIRED_GITIGNORE_ENTRIES = [
    "node_modules/",
    "dist/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    ".env",
    "data/current/",
]


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=check)


def check_required_files(results: dict[str, object]) -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")
    results["required_files"] = "ok"


def check_gitignore(results: dict[str, object]) -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [entry for entry in REQUIRED_GITIGNORE_ENTRIES if entry not in gitignore]
    if missing:
        raise AssertionError(f".gitignore missing generated paths: {missing}")
    results["gitignore"] = "ok"


def check_git_state(results: dict[str, object], require_git: bool) -> None:
    git_root = run(["git", "rev-parse", "--show-toplevel"], check=False)
    if git_root.returncode != 0:
        if require_git:
            raise AssertionError("not a git repository; Render Blueprint deployment needs a pushed Git remote")
        results["git"] = "not-a-git-repository"
        results.setdefault("warnings", []).append("Render Blueprint still needs this directory initialized and pushed to a Git remote.")
        return
    remote = run(["git", "remote", "-v"], check=False)
    results["git"] = git_root.stdout.strip()
    if not remote.stdout.strip():
        if require_git:
            raise AssertionError("git repository has no remote; Render Blueprint deployment needs GitHub/GitLab/Bitbucket")
        results.setdefault("warnings", []).append("Git repository has no remote.")


def check_render_yaml(results: dict[str, object]) -> None:
    config = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = config.get("services") or []
    if len(services) != 1:
        raise AssertionError("render.yaml should define exactly one web service")
    service = services[0]
    expected = {
        "type": "web",
        "name": "xingtu-short-video-bi",
        "runtime": "docker",
        "dockerfilePath": "./Dockerfile",
        "dockerContext": ".",
        "healthCheckPath": "/api/health",
    }
    mismatched = {key: service.get(key) for key, value in expected.items() if service.get(key) != value}
    if mismatched:
        raise AssertionError(f"render.yaml mismatch: {mismatched}")
    env = {item["key"]: item["value"] for item in service.get("envVars", [])}
    if env.get("XINGTU_DATA_DIR") != "/data/current":
        raise AssertionError("render.yaml should set XINGTU_DATA_DIR=/data/current")
    disk = service.get("disk") or {}
    if disk.get("mountPath") != "/data" or int(disk.get("sizeGB", 0)) < 1:
        raise AssertionError("render.yaml should mount a persistent disk at /data with at least 1GB")
    results["render_yaml"] = "ok"


def check_dockerfile(results: dict[str, object]) -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    required = ["npm ci", "npm run build", "pip install --no-cache-dir -r requirements.txt", "uvicorn app.main:app"]
    missing = [item for item in required if item not in dockerfile]
    if missing:
        raise AssertionError(f"Dockerfile missing expected commands: {missing}")
    results["dockerfile"] = "ok"


def check_tests_and_build(results: dict[str, object]) -> None:
    run(["npm", "test"])
    results["frontend_tests"] = "ok"
    run(["npm", "run", "build"])
    results["frontend_build"] = "ok"
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        raise AssertionError(".venv/bin/python missing; run python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
    run([str(python), "-m", "unittest", "discover", "-s", "tests", "-v"])
    results["python_tests"] = "ok"


def check_production_assets(results: dict[str, object]) -> None:
    index = (ROOT / "dist/index.html").read_text(encoding="utf-8")
    if "/assets/" not in index:
        raise AssertionError("dist/index.html should use absolute /assets paths for /admin compatibility")
    if "./assets/" in index:
        raise AssertionError("dist/index.html should not use ./assets paths")
    local_api_hits: list[str] = []
    for asset in (ROOT / "dist/assets").glob("*.js"):
        if "127.0.0.1:8010" in asset.read_text(encoding="utf-8"):
            local_api_hits.append(asset.name)
    if local_api_hits:
        raise AssertionError(f"production JS still references local API: {local_api_hits}")
    results["production_assets"] = "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deployment preflight checks for Xingtu BI.")
    parser.add_argument("--require-git", action="store_true", help="Fail unless the project is a Git repo with a remote.")
    args = parser.parse_args()

    results: dict[str, object] = {"status": "ok", "warnings": []}
    checks = [
        check_required_files,
        check_gitignore,
        lambda output: check_git_state(output, args.require_git),
        check_render_yaml,
        check_dockerfile,
        check_tests_and_build,
        check_production_assets,
    ]

    try:
        for check in checks:
            check(results)
    except Exception as error:
        results["status"] = "failed"
        results["error"] = str(error)
        print(json.dumps(results, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    if not results["warnings"]:
        results.pop("warnings")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
