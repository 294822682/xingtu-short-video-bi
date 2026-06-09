from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from app.default_data import DEFAULT_DATASETS
from app.modules import DEFAULT_MODULE_SLUG, normalize_module_slug

DATASET_FILE_NAMES = {
    "xingtu": "dataset.json",
    "oae": "oae_dataset.json",
}


def data_dir_from_env() -> Path | None:
    data_dir = os.environ.get("BI_DATA_DIR") or os.environ.get("XINGTU_DATA_DIR")
    if not data_dir:
        return None
    return Path(data_dir)


def dataset_path_from_env(module_slug: str = DEFAULT_MODULE_SLUG) -> Path | None:
    data_dir = data_dir_from_env()
    if data_dir is None:
        return None
    slug = normalize_module_slug(module_slug)
    return data_dir / DATASET_FILE_NAMES[slug]


def default_dataset_for_module(module_slug: str = DEFAULT_MODULE_SLUG) -> dict[str, Any]:
    slug = normalize_module_slug(module_slug)
    return copy.deepcopy(DEFAULT_DATASETS[slug])


def load_dataset(dataset_path: Path | None = None, module_slug: str = DEFAULT_MODULE_SLUG) -> dict[str, Any]:
    path = dataset_path if dataset_path is not None else dataset_path_from_env(module_slug)
    if path is None or not path.exists():
        return default_dataset_for_module(module_slug)
    return json.loads(path.read_text(encoding="utf-8"))


def save_dataset(dataset: dict[str, Any], dataset_path: Path | None = None, module_slug: str = DEFAULT_MODULE_SLUG) -> None:
    path = dataset_path if dataset_path is not None else dataset_path_from_env(module_slug)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
