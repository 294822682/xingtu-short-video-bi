from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from app.default_data import DEFAULT_DATASET

DATASET_FILE_NAME = "dataset.json"


def dataset_path_from_env() -> Path | None:
    data_dir = os.environ.get("XINGTU_DATA_DIR")
    if not data_dir:
        return None
    return Path(data_dir) / DATASET_FILE_NAME


def load_dataset(dataset_path: Path | None = None) -> dict[str, Any]:
    path = dataset_path if dataset_path is not None else dataset_path_from_env()
    if path is None or not path.exists():
        return copy.deepcopy(DEFAULT_DATASET)
    return json.loads(path.read_text(encoding="utf-8"))


def save_dataset(dataset: dict[str, Any], dataset_path: Path | None = None) -> None:
    path = dataset_path if dataset_path is not None else dataset_path_from_env()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
