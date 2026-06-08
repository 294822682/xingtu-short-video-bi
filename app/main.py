from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.metrics import build_dataset_from_workbook
from app.storage import load_dataset, save_dataset

app = FastAPI(title="星途短视频经营 BI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"
INDEX_FILE = DIST_DIR / "index.html"
CURRENT_DATASET = load_dataset()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/short-video/overview")
def overview() -> dict:
    return CURRENT_DATASET


@app.post("/api/admin/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        dataset = build_dataset_from_workbook(tmp_path, file.filename)
    finally:
        tmp_path.unlink(missing_ok=True)

    global CURRENT_DATASET
    CURRENT_DATASET = dataset
    save_dataset(dataset)
    return {"status": "ready", **dataset}


if INDEX_FILE.exists():
    assets_dir = DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_route(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        static_file = DIST_DIR / full_path
        if static_file.is_file():
            return FileResponse(static_file)
        return FileResponse(INDEX_FILE)
