from __future__ import annotations

from typing import Any

DEFAULT_MODULE_SLUG = "xingtu"

BI_MODULES: dict[str, dict[str, Any]] = {
    "xingtu": {
        "slug": "xingtu",
        "name": "星途短视频经营 BI",
        "short_name": "星途短视频",
        "eyebrow": "XINGTU SHORT VIDEO BI",
        "description": "面向星途新媒体伙伴的数据可视化 BI，聚焦账号曝光、发布表现和演员贡献。",
        "admin_description": "上传或替换星途短视频 Excel 后，系统会重新生成账号维度、演员维度和 Top/Bot 视频榜单。",
        "status": "ready",
        "parser": "short_video",
        "dashboard_path": "/xingtu",
        "admin_path": "/admin/xingtu",
    },
    "oae": {
        "slug": "oae",
        "name": "OAE 经营 BI",
        "short_name": "OAE",
        "eyebrow": "OAE OPERATIONS BI",
        "description": "面向 OAE 多源经营日报的独立 BI 入口，读取清洗归因后的 dashboard source 数据。",
        "admin_description": "OAE 数据由 Operations Analytics Engine pipeline 生成，本页只读展示最终 dashboard source，不接收原始 Excel 上传。",
        "status": "ready",
        "parser": "oae_dashboard_source",
        "dashboard_path": "/oae",
        "admin_path": "/admin/oae",
    },
}


def public_module_config(slug: str) -> dict[str, Any]:
    module = get_module_config(slug)
    return {
        "slug": module["slug"],
        "name": module["name"],
        "short_name": module["short_name"],
        "eyebrow": module["eyebrow"],
        "description": module["description"],
        "admin_description": module["admin_description"],
        "status": module["status"],
        "dashboard_path": module["dashboard_path"],
        "admin_path": module["admin_path"],
        "upload_enabled": module["parser"] == "short_video",
    }


def module_list() -> list[dict[str, Any]]:
    return [public_module_config(slug) for slug in BI_MODULES]


def get_module_config(slug: str) -> dict[str, Any]:
    normalized = normalize_module_slug(slug)
    return BI_MODULES[normalized]


def normalize_module_slug(slug: str | None) -> str:
    if not slug:
        return DEFAULT_MODULE_SLUG
    normalized = slug.strip().lower()
    aliases = {
        "short-video": "xingtu",
        "short_video": "xingtu",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in BI_MODULES:
        raise KeyError(normalized)
    return normalized
