from __future__ import annotations

import tempfile
import copy
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.metrics import build_dataset_from_workbook
from app.modules import BI_MODULES, DEFAULT_MODULE_SLUG, module_list, normalize_module_slug, public_module_config
from app.storage import load_dataset, save_dataset

app = FastAPI(title="Operations BI Hub")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"
INDEX_FILE = DIST_DIR / "index.html"
CURRENT_DATASETS = {slug: load_dataset(module_slug=slug) for slug in BI_MODULES}


def module_slug_or_404(module_slug: str | None) -> str:
    try:
        return normalize_module_slug(module_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未知 BI 模块") from exc


def dataset_payload(module_slug: str) -> dict:
    slug = module_slug_or_404(module_slug)
    dataset = copy.deepcopy(CURRENT_DATASETS[slug])
    dataset["module"] = public_module_config(slug)
    return dataset


def ensure_xlsx(file: UploadFile) -> None:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")


async def upload_for_module(module_slug: str, file: UploadFile) -> dict:
    slug = module_slug_or_404(module_slug)
    module = BI_MODULES[slug]
    if module["parser"] != "short_video":
        raise HTTPException(status_code=422, detail="该 BI 模块为只读数据源展示，不接收原始 Excel 上传。")

    ensure_xlsx(file)
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        dataset = build_dataset_from_workbook(tmp_path, file.filename or "uploaded.xlsx")
    finally:
        tmp_path.unlink(missing_ok=True)

    video_count = int(dataset.get("overview", {}).get("total_video_count") or 0)
    if video_count == 0:
        raise HTTPException(status_code=422, detail="未识别到有效视频行，请确认 Excel 已保存可见数据后再上传。")

    CURRENT_DATASETS[slug] = dataset
    save_dataset(dataset, module_slug=slug)
    return {"status": "ready", "module": public_module_config(slug), **dataset}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/modules")
def modules() -> dict[str, list[dict]]:
    return {"modules": module_list()}


@app.get("/api/bi/{module_slug}/overview")
def module_overview(module_slug: str) -> dict:
    return dataset_payload(module_slug)


@app.post("/api/bi/{module_slug}/admin/upload")
async def module_upload(module_slug: str, file: UploadFile = File(...)) -> dict:
    return await upload_for_module(module_slug, file)


@app.get("/api/short-video/overview")
def overview() -> dict:
    return dataset_payload(DEFAULT_MODULE_SLUG)


@app.post("/api/admin/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    return await upload_for_module(DEFAULT_MODULE_SLUG, file)


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
