from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SOURCE_PATTERN = "feishu_dashboard_source_latest_*.tsv"
REPORT_DATE_RE = re.compile(r"^feishu_dashboard_source_latest_(\d{4}-\d{2}-\d{2})\.tsv$")
SUMMARY_ACCOUNT_NAMES = {"线索组汇总"}


def load_oae_dataset_from_sources(source_dir: Path | None = None) -> dict[str, Any] | None:
    resolved_source_dir = source_dir or resolve_oae_source_dir()
    if resolved_source_dir is None:
        return None

    latest_path = latest_source_path(resolved_source_dir)
    if latest_path is None:
        return None

    rows = read_dashboard_source(latest_path)
    report_date = rows[0].get("report_date", "") if rows else report_date_from_path(latest_path)
    available_report_dates = available_report_dates_from_sources(resolved_source_dir)
    return build_oae_dataset(
        rows,
        report_date=report_date,
        source_path=latest_path,
        available_report_dates=available_report_dates,
        trend_rows=build_trends(resolved_source_dir),
    )


def resolve_oae_source_dir() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("OAE_DASHBOARD_SOURCE_DIR"):
        candidates.append(Path(os.environ["OAE_DASHBOARD_SOURCE_DIR"]))

    data_dir = os.environ.get("BI_DATA_DIR") or os.environ.get("XINGTU_DATA_DIR")
    if data_dir:
        data_path = Path(data_dir)
        candidates.extend(
            [
                data_path / "oae" / "sql_reports",
                data_path / "sql_reports",
            ]
        )

    candidates.append(Path(__file__).resolve().parents[1] / "data" / "oae" / "sql_reports")

    for candidate in candidates:
        if candidate.exists() and any(candidate.glob(SOURCE_PATTERN)):
            return candidate
    return None


def latest_source_path(source_dir: Path) -> Path | None:
    paths = sorted(
        (path for path in source_dir.glob(SOURCE_PATTERN) if report_date_from_path(path)),
        key=lambda path: report_date_from_path(path),
    )
    return paths[-1] if paths else None


def available_report_dates_from_sources(source_dir: Path) -> list[str]:
    return sorted({report_date_from_path(path) for path in source_dir.glob(SOURCE_PATTERN) if report_date_from_path(path)})


def read_dashboard_source(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def report_date_from_path(path: Path) -> str:
    matched = REPORT_DATE_RE.match(path.name)
    return matched.group(1) if matched else ""


def build_oae_dataset(
    rows: list[dict[str, str]],
    *,
    report_date: str,
    source_path: Path,
    available_report_dates: list[str],
    trend_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    topline = metrics_for(rows, source_table="topline", scope_name="全量")
    seed_account = metrics_for(rows, source_table="seed_account", scope_name="EXEED星途")
    impressions = metric_number(topline, "impressions")
    leads = metric_number(topline, "mtd_unique_leads")
    deals = metric_number(topline, "mtd_deals")
    anchors = entity_rows(rows, source_table="lead_anchor", name_key="anchor_name")

    return {
        "overview": {
            "total_video_count": int(leads or 0),
            "total_exposure": impressions or 0,
            "overall_5s_completion_rate": metric_number(topline, "impressions", field="attain_rate"),
            "overall_5s_completion_rate_display": rate_display(metric_number(topline, "impressions", field="attain_rate")),
            "actor_video_count": int(deals or 0),
            "actor_count": len(anchors),
            "quality_status": "已接入 OAE dashboard source",
            "source_file_name": source_path.name,
            "generated_at": report_date,
            "module_status": "ready",
            "report_date": report_date,
            "source_contract": "feishu_dashboard_source_tsv",
        },
        "account_metrics": legacy_account_rows(rows),
        "actor_metrics": legacy_actor_rows(anchors),
        "video_rankings": {"top": None, "bottom": None},
        "oae_dashboard": {
            "report_date": report_date,
            "available_report_dates": available_report_dates,
            "source": {
                "type": "feishu_dashboard_source_tsv",
                "path": str(source_path),
                "rows": len(rows),
            },
            "kpis": kpi_rows(topline),
            "segments": segment_rows(rows),
            "lead_accounts": entity_rows(rows, source_table="lead_account", name_key="account_name"),
            "lead_anchors": anchors,
            "seed_account": {
                "account_name": "EXEED星途",
                "daily_impressions": metric_number(seed_account, "daily_impressions"),
                "mtd_impressions": metric_number(seed_account, "mtd_impressions"),
                "mtd_impressions_target": metric_number(seed_account, "mtd_impressions", field="target"),
                "mtd_impressions_attain_rate": metric_number(seed_account, "mtd_impressions", field="attain_rate"),
            },
            "seed_anchors": seed_anchor_rows(rows),
            "quality_metrics": quality_rows(rows),
            "trends": trend_rows,
        },
        "quality_report": {
            "used_sheets": ["OAE dashboard source TSV"],
            "excluded_sheets": [],
            "missing_fields": {},
            "sheet_issues": {},
            "invalid_values": {},
            "sheets_without_5s_completion": [],
            "notes": [
                "OAE 数据读取自 feishu_dashboard_source_latest_*.tsv",
                "OAE 多源清洗、归因、日报导出仍由 Operations Analytics Engine 仓库完成",
            ],
        },
    }


def kpi_rows(metrics: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    keys = [
        "impressions",
        "mtd_unique_leads",
        "mtd_douyin_laike_orders",
        "mtd_deals",
        "mtd_spend",
        "mtd_cpl",
        "mtd_cps",
        "pending_cumulative",
    ]
    return [metric_payload(metrics[key]) for key in keys if key in metrics]


def segment_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped = grouped_metrics(rows, "topline_segment")
    segments = []
    for segment_name, metrics in grouped.items():
        segments.append(
            {
                "segment_name": segment_name,
                "mtd_unique_leads": metric_number(metrics, "mtd_unique_leads"),
                "mtd_deals": metric_number(metrics, "mtd_deals"),
                "mtd_spend": metric_number(metrics, "mtd_spend"),
                "mtd_cpl": metric_number(metrics, "mtd_cpl"),
                "mtd_cps": metric_number(metrics, "mtd_cps"),
            }
        )
    return segments


def entity_rows(rows: list[dict[str, str]], *, source_table: str, name_key: str) -> list[dict[str, Any]]:
    grouped = grouped_metrics(rows, source_table)
    entities = []
    for name, metrics in grouped.items():
        if source_table == "lead_account" and name in SUMMARY_ACCOUNT_NAMES:
            continue
        entities.append(
            {
                name_key: name,
                "parent_scope": first_metric(metrics).get("parent_scope", ""),
                "daily_leads": metric_number(metrics, "daily_leads"),
                "mtd_unique_leads": metric_number(metrics, "mtd_unique_leads"),
                "daily_deals": metric_number(metrics, "daily_deals"),
                "mtd_deals": metric_number(metrics, "mtd_deals"),
                "mtd_douyin_laike_orders": metric_number(metrics, "mtd_douyin_laike_orders"),
                "mtd_spend": metric_number(metrics, "mtd_spend"),
                "mtd_cpl": metric_number(metrics, "mtd_cpl"),
                "mtd_cps": metric_number(metrics, "mtd_cps"),
                "sort_order": metric_number(metrics, "mtd_unique_leads", field="sort_order") or 0,
            }
        )
    return sorted(entities, key=lambda item: (-(item.get("mtd_unique_leads") or 0), item.get("sort_order") or 0))


def seed_anchor_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped = grouped_metrics(rows, "seed_anchor")
    anchors = []
    for name, metrics in grouped.items():
        anchors.append(
            {
                "anchor_name": name,
                "daily_impressions": metric_number(metrics, "daily_impressions"),
                "mtd_impressions": metric_number(metrics, "mtd_impressions"),
                "mtd_impressions_target": metric_number(metrics, "mtd_impressions", field="target"),
                "mtd_impressions_attain_rate": metric_number(metrics, "mtd_impressions", field="attain_rate"),
            }
        )
    return sorted(anchors, key=lambda item: -(item.get("mtd_impressions") or 0))


def quality_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [metric_payload(row) for row in rows if row.get("source_table") == "lead_quality"]


def legacy_account_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    accounts = entity_rows(rows, source_table="lead_account", name_key="account_name")
    return [
        {
            "platform": "OAE",
            "account_name": row["account_name"],
            "video_count": int(row.get("daily_leads") or 0),
            "exposure": row.get("mtd_unique_leads") or 0,
            "average_exposure": row.get("mtd_cpl") or 0,
            "completion_5s_display": rate_display(None),
            "completion_field_source": "OAE 不适用",
            "actor_video_count": int(row.get("mtd_deals") or 0),
            "missing_actor_video_count": 0,
        }
        for row in accounts
    ]


def legacy_actor_rows(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "actor_name": row["anchor_name"],
            "video_count": int(row.get("daily_leads") or 0),
            "account_count": 1 if row.get("parent_scope") else 0,
            "contributed_exposure": row.get("mtd_unique_leads") or 0,
            "accounts": row.get("parent_scope") or "未提供",
        }
        for row in anchors
    ]


def build_trends(source_dir: Path) -> list[dict[str, Any]]:
    trends = []
    for path in sorted(source_dir.glob(SOURCE_PATTERN), key=lambda item: report_date_from_path(item)):
        report_date = report_date_from_path(path)
        if not report_date:
            continue
        rows = read_dashboard_source(path)
        topline = metrics_for(rows, source_table="topline", scope_name="全量")
        trends.append(
            {
                "report_date": report_date,
                "impressions": metric_number(topline, "impressions") or 0,
                "mtd_unique_leads": metric_number(topline, "mtd_unique_leads") or 0,
                "mtd_douyin_laike_orders": metric_number(topline, "mtd_douyin_laike_orders") or 0,
                "mtd_deals": metric_number(topline, "mtd_deals") or 0,
                "mtd_spend": metric_number(topline, "mtd_spend") or 0,
            }
        )
    return trends[-31:]


def metrics_for(rows: list[dict[str, str]], *, source_table: str, scope_name: str) -> dict[str, dict[str, str]]:
    return {
        row["metric_key"]: row
        for row in rows
        if row.get("source_table") == source_table and row.get("scope_name") == scope_name and row.get("metric_key")
    }


def grouped_metrics(rows: list[dict[str, str]], source_table: str) -> dict[str, dict[str, dict[str, str]]]:
    grouped: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        if row.get("source_table") != source_table:
            continue
        scope_name = row.get("scope_name", "")
        metric_key = row.get("metric_key", "")
        if scope_name and metric_key:
            grouped[scope_name][metric_key] = row
    return dict(grouped)


def metric_payload(row: dict[str, str]) -> dict[str, Any]:
    return {
        "metric_key": row.get("metric_key", ""),
        "metric_name": row.get("metric_name", ""),
        "actual": parse_number(row.get("actual", "")),
        "target": parse_number(row.get("target", "")),
        "attain_rate": parse_number(row.get("attain_rate", "")),
        "unit": row.get("unit", ""),
        "source_column": row.get("source_column", ""),
    }


def metric_number(metrics: dict[str, dict[str, str]], key: str, *, field: str = "actual") -> float | None:
    return parse_number(metrics.get(key, {}).get(field, ""))


def parse_number(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    normalized = str(value).strip().replace(",", "")
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def rate_display(value: float | None) -> str:
    if value is None:
        return "未提供"
    return f"{value * 100:.1f}%"


def first_metric(metrics: dict[str, dict[str, str]]) -> dict[str, str]:
    return next(iter(metrics.values()), {})
