# Feishu HTTPS Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `xingtu-short-video-bi` deployable as a single HTTPS web app suitable for Feishu iframe acceptance.

**Architecture:** Build the React frontend into `dist/`, serve it from FastAPI together with `/api/*`, and deploy the whole app as one Docker web service. Persist uploaded BI data through `XINGTU_DATA_DIR/dataset.json` so manual Excel refresh survives service restarts.

**Tech Stack:** React + Vite, FastAPI, Docker, Render Blueprint.

---

### Task 1: Single-service production app

**Files:**
- Modify: `app/main.py`
- Modify: `frontend/src/main.jsx`
- Modify: `vite.config.js`

- [x] Serve `dist/index.html` and `/assets/*` from FastAPI when `dist/` exists.
- [x] Keep `/api/*` as API-only paths.
- [x] Use relative API URLs in production and `http://127.0.0.1:8010` in Vite dev.
- [x] Build with absolute `/assets/...` paths for `/admin` iframe compatibility.

### Task 2: Upload data persistence

**Files:**
- Create: `app/storage.py`
- Create: `tests/test_storage.py`
- Modify: `app/main.py`

- [x] Load default data when `XINGTU_DATA_DIR` is not set or no persisted file exists.
- [x] Save uploaded dataset to `XINGTU_DATA_DIR/dataset.json` when the env var is set.
- [x] Verify Chinese source file names round-trip through JSON.

### Task 3: Deploy artifacts

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `render.yaml`
- Create: `docs/feishu-deploy.md`

- [x] Build frontend in a Node 24 stage.
- [x] Run FastAPI in a Python 3.12 runtime stage.
- [x] Configure Render Docker web service with `/api/health` health check.
- [x] Mount persistent disk to `/data` and set `XINGTU_DATA_DIR=/data/current`.
- [x] Document Feishu iframe acceptance checks.

### Task 4: Verification

**Commands:**

```bash
npm test
npm run build
.venv/bin/python -m unittest discover -s tests -v
XINGTU_DATA_DIR="$(mktemp -d)" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8020
```

Expected:

- Frontend tests pass.
- Vite production build passes.
- Python unittest passes.
- `http://127.0.0.1:8020/`, `/admin`, and `/api/health` all respond.
