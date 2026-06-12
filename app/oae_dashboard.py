from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any


SOURCE_PATTERN = "feishu_dashboard_source_latest_*.tsv"
REPORT_DATE_RE = re.compile(r"^feishu_dashboard_source_latest_(\d{4}-\d{2}-\d{2})\.tsv$")
SUMMARY_ACCOUNT_NAMES = {"线索组汇总"}
DEPARTED_ANCHOR_NAMES = {"王馨", "曹嘉洋"}
BUSINESS_LABEL_OVERRIDES = {
    "mtd_unique_leads": "风车线索（去重）",
    "mtd_douyin_laike_orders": "抖音来客订单（去重）",
}
BUSINESS_SUMMARY_METRIC_KEYS = {
    "mtd_unique_leads",
    "mtd_douyin_laike_orders",
    "mtd_deals",
    "mtd_spend",
    "mtd_cpl",
    "mtd_cps",
}
LEAD_ACCOUNT_CORE_METRIC_KEYS = {
    "daily_leads",
    "mtd_unique_leads",
    "mtd_douyin_laike_orders",
    "daily_deals",
    "mtd_deals",
    "mtd_spend",
    "mtd_cpl",
    "mtd_cps",
}
RANGE_CUMULATIVE_METRIC_KEYS = {
    "mtd_unique_leads",
    "mtd_douyin_laike_orders",
    "mtd_deals",
    "mtd_spend",
    "visits",
    "visit_deals",
}
RANGE_DAILY_METRIC_KEYS = {"daily_leads", "daily_deals"}
SEED_CUMULATIVE_METRIC_KEYS = {"mtd_impressions"}
SEED_DAILY_METRIC_KEYS = {"daily_impressions"}


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

    available: list[tuple[str, int, Path]] = []
    for index, candidate in enumerate(candidates):
        if not candidate.exists():
            continue
        latest_path = latest_source_path(candidate)
        if latest_path is None:
            continue
        available.append((report_date_from_path(latest_path), index, candidate))
    if not available:
        return None
    return max(available, key=lambda item: (item[0], -item[1]))[2]


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
    topline = business_summary_metrics(rows)
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
        if source_table in {"lead_anchor", "seed_anchor"} and name in DEPARTED_ANCHOR_NAMES:
            continue
        if source_table == "lead_account" and name in SUMMARY_ACCOUNT_NAMES:
            continue
        if source_table == "lead_account" and not has_any_metric(metrics, LEAD_ACCOUNT_CORE_METRIC_KEYS):
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
        if name in DEPARTED_ANCHOR_NAMES:
            continue
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
        topline = business_summary_metrics(rows)
        trends.append(
            {
                "report_date": report_date,
                "impressions": metric_number(topline, "impressions") or 0,
                "mtd_unique_leads": metric_number(topline, "mtd_unique_leads") or 0,
                "mtd_douyin_laike_orders": metric_number(topline, "mtd_douyin_laike_orders") or 0,
                "mtd_deals": metric_number(topline, "mtd_deals") or 0,
                "mtd_spend": metric_number(topline, "mtd_spend") or 0,
                "mtd_cpl": metric_number(topline, "mtd_cpl") or 0,
                "mtd_cps": metric_number(topline, "mtd_cps") or 0,
            }
        )
    return trends


def load_oae_daily_dashboard_payload(report_date: str = "latest", source_dir: Path | None = None) -> dict[str, Any]:
    resolved_source_dir = source_dir or resolve_oae_source_dir()
    if resolved_source_dir is None:
        raise FileNotFoundError("No OAE dashboard source directory found")

    source_path = resolve_source_path(resolved_source_dir, report_date)
    rows = read_dashboard_source(source_path)
    resolved_report_date = rows[0].get("report_date", "") if rows else report_date_from_path(source_path)
    available_dates = available_report_dates_from_sources(resolved_source_dir)
    topline = business_summary_metrics(rows)
    lead_quality = metrics_for(rows, source_table="lead_quality", scope_name="全量")
    overview = {
        "impressions": dashboard_metric_payload(topline, "impressions", "曝光"),
        "mtd_unique_leads": dashboard_metric_payload(topline, "mtd_unique_leads", "风车线索（去重）"),
        "mtd_douyin_laike_orders": dashboard_metric_payload(topline, "mtd_douyin_laike_orders", "抖音来客订单（去重）"),
        "mtd_deals": dashboard_metric_payload(topline, "mtd_deals", "实销"),
        "mtd_spend": dashboard_metric_payload(topline, "mtd_spend", "费用"),
        "mtd_cpl": dashboard_metric_payload(topline, "mtd_cpl", "CPL"),
        "mtd_cps": dashboard_metric_payload(topline, "mtd_cps", "CPS"),
        "pending_day": dashboard_metric_payload(topline, "pending_day", "待交车（当日）"),
        "pending_cumulative": dashboard_metric_payload(topline, "pending_cumulative", "待交车（累计）"),
        "raw_leads": dashboard_metric_payload(lead_quality, "raw_leads", "线索"),
        "unique_rate": dashboard_metric_payload(lead_quality, "unique_rate", "唯一率"),
        "unowned_leads": dashboard_metric_payload(lead_quality, "unowned_leads", "无主线索"),
        "manual_overrides": dashboard_metric_payload(lead_quality, "manual_overrides", "人工归属"),
    }
    if not overview["raw_leads"]["actual"]:
        overview["raw_leads"] = dashboard_metric_payload(lead_quality, "lead_quality_unique_leads", "线索")

    return {
        "report_date": resolved_report_date,
        "available_report_dates": available_dates,
        "source": {
            "type": "feishu_dashboard_source_tsv",
            "path": public_source_path(source_path),
            "rows": len(rows),
        },
        "overview": overview,
        "funnel": dashboard_funnel(overview),
        "account_summary": dashboard_entities(rows, source_table="lead_account", name_key="account_name", include_summary=True),
        "lead_anchors": dashboard_entities(rows, source_table="lead_anchor", name_key="anchor_name"),
        "seed_account": dashboard_metric_payload(
            metrics_for(rows, source_table="seed_account", scope_name="EXEED星途"),
            "mtd_impressions",
            "EXEED星途累计曝光",
        ),
        "seed_anchors": dashboard_entities(rows, source_table="seed_anchor", name_key="anchor_name"),
        "interactions": {
            "module_anchors": ["overview", "funnel", "lead-anchors", "seed-exposure", "daily-bi-trends"],
            "lead_anchor_sort_keys": ["mtd_unique_leads", "mtd_douyin_laike_orders", "visits", "mtd_cpl"],
            "seed_anchor_sort_keys": ["mtd_impressions", "mtd_impressions_attain_rate"],
        },
    }


def load_oae_trends_payload(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    resolved_source_dir = source_dir or resolve_oae_source_dir()
    if resolved_source_dir is None:
        raise FileNotFoundError("No OAE dashboard source directory found")

    snapshots = dashboard_source_snapshots(resolved_source_dir)
    all_report_dates = [snapshot["report_date"] for snapshot in snapshots]
    latest_available_date = all_report_dates[-1] if all_report_dates else ""
    all_rows = build_trends(resolved_source_dir)
    if not all_rows:
        raise FileNotFoundError("No OAE dashboard source found for trend range")

    resolved_end_date = end_date or latest_available_date
    resolved_start_date = start_date or default_trend_start_for_end(resolved_end_date)
    rows = [
        row
        for row in all_rows
        if row["report_date"] >= resolved_start_date and row["report_date"] <= resolved_end_date
    ]
    if not rows:
        raise FileNotFoundError("No OAE dashboard source found for trend range")
    filtered_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot["report_date"] >= resolved_start_date and snapshot["report_date"] <= resolved_end_date
    ]

    first_date = rows[0]["report_date"]
    last_date = rows[-1]["report_date"]
    latest_rows = filtered_snapshots[-1]["rows"] if filtered_snapshots else read_dashboard_source(resolve_source_path(resolved_source_dir, last_date))
    latest_topline = business_summary_metrics(latest_rows)
    available_dates = [row["report_date"] for row in rows]
    calendar_dates = calendar_date_strings(resolved_start_date, resolved_end_date)
    available_date_set = set(available_dates)
    missing_dates = [date_key for date_key in calendar_dates if date_key not in available_date_set]
    selected_days = len(calendar_dates)
    trend_specs = [
        ("impressions", "曝光", "人次", "impressions"),
        ("leads", "风车线索（去重）", "条", "mtd_unique_leads"),
        ("douyin_laike_orders", "抖音来客订单（去重）", "条", "mtd_douyin_laike_orders"),
        ("deals", "实销", "台", "mtd_deals"),
        ("spend", "费用", "元", "mtd_spend"),
        ("cpl", "CPL", "元/条", "mtd_cpl"),
        ("cps", "CPS", "元/台", "mtd_cps"),
    ]
    daily_trends = [
        {
            "key": key,
            "label": label,
            "unit": unit,
            "points": [{"date": row["report_date"], "value": row.get(source_key, 0)} for row in rows],
        }
        for key, label, unit, source_key in trend_specs
    ]
    core_kpi_summary = [
        trend_metric_payload(latest_topline, source_key, key, label)
        for key, label, unit, source_key in trend_specs
    ]
    return {
        "contract_version": "oae-dashboard-source-adapter-v1",
        "date_range": {
            "start": resolved_start_date,
            "end": resolved_end_date,
            "start_date": resolved_start_date,
            "end_date": resolved_end_date,
            "days": selected_days,
            "selected_range_days": selected_days,
            "date_count": len(rows),
            "available_dates": available_dates,
            "all_available_dates": all_report_dates,
            "latest_available_date": latest_available_date,
            "missing_dates": missing_dates,
        },
        "selected_range_days": selected_days,
        "available_dates": available_dates,
        "all_available_dates": all_report_dates,
        "latest_available_date": latest_available_date,
        "missing_dates": missing_dates,
        "source_type": "feishu_dashboard_source_tsv_history",
        "source": {
            "type": "feishu_dashboard_source_tsv_history",
            "paths": available_dates,
            "rows": len(rows),
            "date_range_label": f"{first_date} 至 {last_date}",
        },
        "core_kpi_summary": core_kpi_summary,
        "daily_trends": daily_trends,
        "previous_period_summary": [],
        "previous_period_trends": [],
        "monthly_comparison": monthly_comparison_rows(daily_trends),
        "account_summary": trend_account_summary(snapshots, filtered_snapshots),
        "anchor_summary": trend_anchor_summary(snapshots, filtered_snapshots),
        "seed_exposure_summary": trend_seed_exposure_summary(snapshots, filtered_snapshots),
        "quality_note": "仅基于 feishu_dashboard_source_latest_*.tsv 历史文件派生。",
    }


def resolve_source_path(source_dir: Path, report_date: str) -> Path:
    if report_date == "latest":
        latest = latest_source_path(source_dir)
        if latest is None:
            raise FileNotFoundError("No OAE dashboard source TSV found")
        return latest
    source_path = source_dir / f"feishu_dashboard_source_latest_{report_date}.tsv"
    if not source_path.exists():
        raise FileNotFoundError(f"OAE dashboard source TSV not found for {report_date}")
    return source_path


def default_trend_start_for_end(end_date: str) -> str:
    end = date.fromisoformat(end_date)
    month_index = end.year * 12 + end.month - 1 - 2
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1).isoformat()


def calendar_date_strings(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    out: list[str] = []
    current = start
    while current <= end:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def dashboard_metric_payload(
    metrics: dict[str, dict[str, str]],
    key: str,
    default_label: str,
    *,
    missing_as_zero: bool = False,
) -> dict[str, Any]:
    row = metrics.get(key, {})
    actual = parse_number(row.get("actual", ""))
    connected = key in metrics and actual is not None
    if actual is None and missing_as_zero:
        actual = 0
    return {
        "key": key,
        "label": BUSINESS_LABEL_OVERRIDES.get(key) or row.get("metric_name") or default_label,
        "actual": actual,
        "target": parse_number(row.get("target", "")),
        "attain_rate": parse_number(row.get("attain_rate", "")),
        "unit": normalize_unit(row.get("unit", "")),
        "note": row.get("source_column", ""),
        "source_column": row.get("source_column", ""),
        "source_status": "available" if connected else "not_connected",
    }


def dashboard_entities(
    rows: list[dict[str, str]],
    *,
    source_table: str,
    name_key: str,
    include_summary: bool = False,
) -> list[dict[str, Any]]:
    grouped = grouped_metrics(rows, source_table)
    out = []
    for name, metrics in grouped.items():
        if source_table in {"lead_anchor", "seed_anchor"} and name in DEPARTED_ANCHOR_NAMES:
            continue
        if source_table == "lead_account" and name in SUMMARY_ACCOUNT_NAMES and not include_summary:
            continue
        if source_table == "lead_account" and not has_any_metric(metrics, LEAD_ACCOUNT_CORE_METRIC_KEYS):
            continue
        metrics_payload = {
            "daily_leads": dashboard_metric_payload(metrics, "daily_leads", "当日线索"),
            "mtd_unique_leads": dashboard_metric_payload(metrics, "mtd_unique_leads", "风车线索（去重）"),
            "mtd_douyin_laike_orders": dashboard_metric_payload(metrics, "mtd_douyin_laike_orders", "抖音来客订单（去重）"),
            "visits": dashboard_metric_payload(metrics, "visits", "到店数", missing_as_zero=False),
            "visit_rate": dashboard_metric_payload(metrics, "visit_rate", "到店率", missing_as_zero=False),
            "visit_deal_rate": dashboard_metric_payload(metrics, "visit_deal_rate", "到店成交率", missing_as_zero=False),
            "daily_deals": dashboard_metric_payload(metrics, "daily_deals", "当日实销"),
            "mtd_deals": dashboard_metric_payload(metrics, "mtd_deals", "累计实销"),
            "mtd_spend": dashboard_metric_payload(metrics, "mtd_spend", "费用"),
            "mtd_cpl": dashboard_metric_payload(metrics, "mtd_cpl", "CPL"),
            "mtd_cps": dashboard_metric_payload(metrics, "mtd_cps", "CPS"),
            "daily_impressions": dashboard_metric_payload(metrics, "daily_impressions", "当日曝光"),
            "mtd_impressions": dashboard_metric_payload(metrics, "mtd_impressions", "累计曝光"),
        }
        mark_zero_denominator_visit_metrics(metrics_payload)
        mark_invalid_visit_rate(metrics_payload)
        mark_invalid_visit_deal_rate(metrics_payload)
        item = {
            "name": name,
            name_key: name,
            "parent_scope": first_metric(metrics).get("parent_scope", ""),
            "metrics": metrics_payload,
        }
        item["metric_groups"] = dashboard_entity_metric_groups(item["metrics"])
        item["mtd_impressions_attain_rate"] = item["metrics"]["mtd_impressions"]["attain_rate"]
        out.append(item)
    return sorted(
        out,
        key=lambda item: (
            -float(item["metrics"].get("mtd_unique_leads", {}).get("actual") or 0),
            -float(item["metrics"].get("mtd_impressions", {}).get("actual") or 0),
            item["name"],
        ),
    )


def dashboard_entity_metric_groups(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    groups: dict[str, dict[str, dict[str, Any]]] = {
        "线索": {
            "daily_leads": metrics["daily_leads"],
            "mtd_unique_leads": metrics["mtd_unique_leads"],
            "mtd_douyin_laike_orders": metrics["mtd_douyin_laike_orders"],
        },
        "成交": {
            "daily_deals": metrics["daily_deals"],
            "mtd_deals": metrics["mtd_deals"],
        },
        "成本": {
            "mtd_spend": metrics["mtd_spend"],
            "mtd_cpl": metrics["mtd_cpl"],
            "mtd_cps": metrics["mtd_cps"],
        },
    }
    visit_metrics = {
        key: metrics[key]
        for key in ("visits", "visit_rate", "visit_deal_rate")
        if metrics[key].get("source_status") in {"available", "not_applicable"}
    }
    if visit_metrics:
        groups["到店"] = visit_metrics
    return groups


def dashboard_funnel(overview: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    steps = [
        ("impressions", "曝光"),
        ("raw_leads", "原始线索"),
        ("mtd_unique_leads", "风车线索（去重）"),
        ("mtd_douyin_laike_orders", "抖音来客订单（去重）"),
        ("mtd_deals", "实销"),
    ]
    out = []
    previous: float | None = None
    for key, label in steps:
        metric = overview.get(key, {})
        actual = float(metric.get("actual") or 0)
        conversion = actual / previous if previous and previous > 0 else None
        out.append(
            {
                "key": key,
                "label": label,
                "actual": actual,
                "unit": metric.get("unit", ""),
                "conversion_from_previous": conversion,
            }
        )
        previous = actual
    return out


def dashboard_source_snapshots(source_dir: Path) -> list[dict[str, Any]]:
    snapshots = []
    for path in sorted(source_dir.glob(SOURCE_PATTERN), key=lambda item: report_date_from_path(item)):
        report_date = report_date_from_path(path)
        if not report_date:
            continue
        snapshots.append({"report_date": report_date, "rows": read_dashboard_source(path)})
    return snapshots


def business_metric_payload(
    metrics: dict[str, dict[str, str]],
    source_key: str,
    key: str,
    default_label: str,
    *,
    missing_as_zero: bool = False,
) -> dict[str, Any]:
    payload = dashboard_metric_payload(metrics, source_key, default_label, missing_as_zero=missing_as_zero)
    payload["key"] = key
    if payload.get("unit") == "次":
        payload["unit"] = "人次"
    if payload.get("target") == 0:
        payload["target"] = None
    return payload


def trend_metric_payload(metrics: dict[str, dict[str, str]], source_key: str, key: str, default_label: str) -> dict[str, Any]:
    payload = business_metric_payload(metrics, source_key, key, default_label)
    payload["value"] = payload.get("actual")
    return payload


def trend_points(
    snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> list[dict[str, Any]]:
    points = []
    for snapshot in snapshots:
        metrics = metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        points.append({"date": snapshot["report_date"], "value": metric_number(metrics, metric_key)})
    return points


def entity_names_from_snapshots(snapshots: list[dict[str, Any]], source_table: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        for name in grouped_metrics(snapshot["rows"], source_table).keys():
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def canonical_scope_name(source_table: str, scope_name: str) -> str:
    name = str(scope_name or "").strip()
    if source_table == "seed_account":
        for prefix in ("抖音-", "快手-"):
            if name.startswith(prefix):
                return name[len(prefix) :]
    return name


def canonical_entity_names_from_snapshots(snapshots: list[dict[str, Any]], source_table: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        for name in grouped_metrics(snapshot["rows"], source_table).keys():
            canonical = canonical_scope_name(source_table, name)
            if canonical and canonical not in seen:
                seen.add(canonical)
                names.append(canonical)
    return names


def canonical_metrics_for(
    rows: list[dict[str, str]],
    *,
    source_table: str,
    scope_name: str,
) -> dict[str, dict[str, str]]:
    canonical_name = canonical_scope_name(source_table, scope_name)
    for raw_name, metrics in grouped_metrics(rows, source_table).items():
        if canonical_scope_name(source_table, raw_name) == canonical_name:
            out = {key: dict(value) for key, value in metrics.items()}
            for row in out.values():
                row["scope_name"] = canonical_name
            return out
    return {}


def latest_entity_metrics(
    snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
) -> dict[str, dict[str, str]]:
    for snapshot in reversed(snapshots):
        metrics = metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        if metrics:
            return metrics
    return {}


def latest_canonical_entity_metrics(
    snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
) -> dict[str, dict[str, str]]:
    for snapshot in reversed(snapshots):
        metrics = canonical_metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        if metrics:
            return metrics
    return {}


def previous_month_snapshot(
    snapshots: list[dict[str, Any]],
    *,
    month: str,
    before_date: str,
) -> dict[str, Any] | None:
    previous = [
        snapshot
        for snapshot in snapshots
        if snapshot["report_date"].startswith(month) and snapshot["report_date"] < before_date
    ]
    return previous[-1] if previous else None


def range_cumulative_value(
    all_snapshots: list[dict[str, Any]],
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> float | None:
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in filtered_snapshots:
        by_month[snapshot["report_date"][:7]].append(snapshot)

    total = 0.0
    connected = False
    for month, month_snapshots in sorted(by_month.items()):
        first_snapshot = month_snapshots[0]
        last_snapshot = month_snapshots[-1]
        last_metrics = metrics_for(last_snapshot["rows"], source_table=source_table, scope_name=scope_name)
        last_value = metric_number(last_metrics, metric_key)
        if last_value is None:
            continue
        baseline = previous_month_snapshot(
            all_snapshots,
            month=month,
            before_date=first_snapshot["report_date"],
        )
        baseline_value = None
        if baseline is not None:
            baseline_metrics = metrics_for(baseline["rows"], source_table=source_table, scope_name=scope_name)
            baseline_value = metric_number(baseline_metrics, metric_key)
        total += last_value - baseline_value if baseline_value is not None else last_value
        connected = True
    return total if connected else None


def range_daily_value(
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> float | None:
    total = 0.0
    connected = False
    for snapshot in filtered_snapshots:
        metrics = metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        value = metric_number(metrics, metric_key)
        if value is None:
            continue
        total += value
        connected = True
    return total if connected else None


def range_canonical_cumulative_value(
    all_snapshots: list[dict[str, Any]],
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> float | None:
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in filtered_snapshots:
        by_month[snapshot["report_date"][:7]].append(snapshot)

    total = 0.0
    connected = False
    for month, month_snapshots in sorted(by_month.items()):
        first_snapshot = month_snapshots[0]
        last_snapshot = month_snapshots[-1]
        last_metrics = canonical_metrics_for(last_snapshot["rows"], source_table=source_table, scope_name=scope_name)
        last_value = metric_number(last_metrics, metric_key)
        if last_value is None:
            continue
        baseline = previous_month_snapshot(
            all_snapshots,
            month=month,
            before_date=first_snapshot["report_date"],
        )
        baseline_value = None
        if baseline is not None:
            baseline_metrics = canonical_metrics_for(baseline["rows"], source_table=source_table, scope_name=scope_name)
            baseline_value = metric_number(baseline_metrics, metric_key)
        total += last_value - baseline_value if baseline_value is not None else last_value
        connected = True
    return total if connected else None


def range_canonical_daily_value(
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> float | None:
    total = 0.0
    connected = False
    for snapshot in filtered_snapshots:
        metrics = canonical_metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        value = metric_number(metrics, metric_key)
        if value is None:
            continue
        total += value
        connected = True
    return total if connected else None


def range_metric_row(
    latest_metrics: dict[str, dict[str, str]],
    metric_key: str,
    actual: float | None,
    *,
    label: str,
    unit: str,
    source_table: str,
    scope_name: str,
) -> dict[str, str]:
    template = dict(latest_metrics.get(metric_key, {}))
    template["metric_key"] = metric_key
    template["metric_name"] = BUSINESS_LABEL_OVERRIDES.get(metric_key) or template.get("metric_name") or label
    template["actual"] = "" if actual is None else str(actual)
    template["target"] = ""
    template["attain_rate"] = ""
    template["unit"] = template.get("unit") or unit
    template["source_column"] = f"range_aggregate.{source_table}.{scope_name}.{metric_key}"
    return template


def range_lead_metrics(
    all_snapshots: list[dict[str, Any]],
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
) -> dict[str, dict[str, str]]:
    latest_metrics = latest_entity_metrics(filtered_snapshots, source_table=source_table, scope_name=scope_name)
    rows: dict[str, dict[str, str]] = {}
    metric_defaults = {
        "daily_leads": ("当日线索", "条"),
        "mtd_unique_leads": ("风车线索（去重）", "条"),
        "mtd_douyin_laike_orders": ("抖音来客订单（去重）", "条"),
        "visits": ("到店数", "条"),
        "visit_deals": ("到店成交数", "台"),
        "visit_rate": ("到店率", "比例"),
        "visit_deal_rate": ("到店成交率", "比例"),
        "daily_deals": ("当日实销", "台"),
        "mtd_deals": ("累计实销", "台"),
        "mtd_spend": ("费用", "元"),
        "mtd_cpl": ("CPL", "元/条"),
        "mtd_cps": ("CPS", "元/台"),
    }
    for metric_key in RANGE_CUMULATIVE_METRIC_KEYS:
        label, unit = metric_defaults[metric_key]
        rows[metric_key] = range_metric_row(
            latest_metrics,
            metric_key,
            range_cumulative_value(
                all_snapshots,
                filtered_snapshots,
                source_table=source_table,
                scope_name=scope_name,
                metric_key=metric_key,
            ),
            label=label,
            unit=unit,
            source_table=source_table,
            scope_name=scope_name,
        )
    for metric_key in RANGE_DAILY_METRIC_KEYS:
        label, unit = metric_defaults[metric_key]
        rows[metric_key] = range_metric_row(
            latest_metrics,
            metric_key,
            range_daily_value(
                filtered_snapshots,
                source_table=source_table,
                scope_name=scope_name,
                metric_key=metric_key,
            ),
            label=label,
            unit=unit,
            source_table=source_table,
            scope_name=scope_name,
        )

    leads = metric_number(rows, "mtd_unique_leads")
    deals = metric_number(rows, "mtd_deals")
    spend = metric_number(rows, "mtd_spend")
    visits = metric_number(rows, "visits")
    visit_deals = metric_number(rows, "visit_deals")
    derived_values = {
        "mtd_cpl": spend / leads if spend is not None and leads and leads > 0 else None,
        "mtd_cps": spend / deals if spend is not None and deals and deals > 0 else None,
        "visit_rate": visits / leads if visits is not None and leads and leads > 0 else None,
        "visit_deal_rate": visit_deals / visits if visit_deals is not None and visits and visits > 0 else None,
    }
    for metric_key, actual in derived_values.items():
        label, unit = metric_defaults[metric_key]
        rows[metric_key] = range_metric_row(
            latest_metrics,
            metric_key,
            actual,
            label=label,
            unit=unit,
            source_table=source_table,
            scope_name=scope_name,
        )
    return rows


def lead_metrics_for_trend(
    metrics: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    out = {
        "leads": business_metric_payload(metrics, "mtd_unique_leads", "leads", "风车线索（去重）"),
        "unique_leads": business_metric_payload(metrics, "mtd_unique_leads", "unique_leads", "风车线索（去重）"),
        "douyin_laike_orders": business_metric_payload(metrics, "mtd_douyin_laike_orders", "douyin_laike_orders", "抖音来客订单（去重）"),
        "visits": business_metric_payload(metrics, "visits", "visits", "到店数", missing_as_zero=False),
        "visit_rate": business_metric_payload(metrics, "visit_rate", "visit_rate", "到店率", missing_as_zero=False),
        "visit_deal_rate": business_metric_payload(metrics, "visit_deal_rate", "visit_deal_rate", "到店成交率", missing_as_zero=False),
        "deals": business_metric_payload(metrics, "mtd_deals", "deals", "累计实销"),
        "spend": business_metric_payload(metrics, "mtd_spend", "spend", "费用"),
        "cpl": business_metric_payload(metrics, "mtd_cpl", "cpl", "CPL"),
        "cps": business_metric_payload(metrics, "mtd_cps", "cps", "CPS"),
        "daily_leads": business_metric_payload(metrics, "daily_leads", "daily_leads", "当日线索"),
        "daily_deals": business_metric_payload(metrics, "daily_deals", "daily_deals", "当日实销"),
        "lead_deal_rate": {
            "key": "lead_deal_rate",
            "label": "线索成交率",
            "actual": lead_deal_rate(metrics),
            "target": None,
            "attain_rate": None,
            "unit": "比例",
        },
    }
    mark_zero_denominator_visit_metrics(out)
    mark_invalid_visit_rate(out)
    mark_invalid_visit_deal_rate(out)
    return out


def range_seed_metrics(
    all_snapshots: list[dict[str, Any]],
    filtered_snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
) -> dict[str, dict[str, str]]:
    latest_metrics = latest_canonical_entity_metrics(filtered_snapshots, source_table=source_table, scope_name=scope_name)
    rows: dict[str, dict[str, str]] = {}
    metric_defaults = {
        "daily_impressions": ("当日曝光", "人次"),
        "mtd_impressions": ("累计曝光", "人次"),
    }
    for metric_key in SEED_CUMULATIVE_METRIC_KEYS:
        label, unit = metric_defaults[metric_key]
        rows[metric_key] = range_metric_row(
            latest_metrics,
            metric_key,
            range_canonical_cumulative_value(
                all_snapshots,
                filtered_snapshots,
                source_table=source_table,
                scope_name=scope_name,
                metric_key=metric_key,
            ),
            label=label,
            unit=unit,
            source_table=source_table,
            scope_name=scope_name,
        )
    for metric_key in SEED_DAILY_METRIC_KEYS:
        label, unit = metric_defaults[metric_key]
        rows[metric_key] = range_metric_row(
            latest_metrics,
            metric_key,
            range_canonical_daily_value(
                filtered_snapshots,
                source_table=source_table,
                scope_name=scope_name,
                metric_key=metric_key,
            ),
            label=label,
            unit=unit,
            source_table=source_table,
            scope_name=scope_name,
        )
    return rows


def mark_zero_denominator_visit_metrics(metrics: dict[str, dict[str, Any]]) -> None:
    visits = metrics.get("visits", {})
    visit_deal_rate = metrics.get("visit_deal_rate", {})
    visits_actual = visits.get("actual")
    if (
        visits.get("source_status") == "available"
        and visits_actual is not None
        and float(visits_actual) == 0
        and visit_deal_rate.get("actual") is None
    ):
        visit_deal_rate["source_status"] = "not_applicable"
        visit_deal_rate["note"] = "到店数为 0，无法计算到店成交率"
        visit_deal_rate["source_column"] = visit_deal_rate.get("source_column") or "derived.zero_visit_denominator"


def mark_invalid_visit_deal_rate(metrics: dict[str, dict[str, Any]]) -> None:
    visit_deal_rate = metrics.get("visit_deal_rate", {})
    actual = visit_deal_rate.get("actual")
    if actual is None:
        return
    if float(actual) <= 1:
        return
    visit_deal_rate["actual"] = None
    visit_deal_rate["source_status"] = "not_applicable"
    visit_deal_rate["note"] = "到店成交数大于到店数，无法计算到店成交率"
    visit_deal_rate["source_column"] = visit_deal_rate.get("source_column") or "derived.invalid_visit_deal_rate"


def mark_invalid_visit_rate(metrics: dict[str, dict[str, Any]]) -> None:
    visit_rate = metrics.get("visit_rate", {})
    actual = visit_rate.get("actual")
    if actual is None:
        return
    if float(actual) <= 1:
        return
    visit_rate["actual"] = None
    visit_rate["source_status"] = "not_applicable"
    visit_rate["note"] = "到店数大于风车线索数，无法计算到店率"
    visit_rate["source_column"] = visit_rate.get("source_column") or "derived.invalid_visit_rate"


def lead_deal_rate(metrics: dict[str, dict[str, str]]) -> float | None:
    leads = metric_number(metrics, "mtd_unique_leads")
    deals = metric_number(metrics, "mtd_deals")
    if not leads or leads <= 0 or deals is None:
        return None
    return deals / leads


def trend_account_summary(all_snapshots: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities = []
    for name in entity_names_from_snapshots(snapshots, "lead_account"):
        metrics = range_lead_metrics(all_snapshots, snapshots, source_table="lead_account", scope_name=name)
        if name not in SUMMARY_ACCOUNT_NAMES and not has_any_metric(metrics, LEAD_ACCOUNT_CORE_METRIC_KEYS):
            continue
        latest_metrics = latest_entity_metrics(snapshots, source_table="lead_account", scope_name=name)
        entities.append(
            {
                "name": name,
                "account_name": name,
                "parent_scope": first_metric(latest_metrics).get("parent_scope") or "账号汇总",
                "sort_order": metric_number(latest_metrics, "mtd_unique_leads", field="sort_order") or 0,
                "metrics": lead_metrics_for_trend(metrics),
                "daily_trends": {
                    "leads": trend_points(snapshots, source_table="lead_account", scope_name=name, metric_key="mtd_unique_leads"),
                    "deals": trend_points(snapshots, source_table="lead_account", scope_name=name, metric_key="mtd_deals"),
                },
            }
        )
    return sorted(
        entities,
        key=lambda item: (
            item["name"] != "线索组汇总",
            -(item["metrics"].get("leads", {}).get("actual") or 0),
            item["sort_order"],
        ),
    )


def trend_anchor_summary(all_snapshots: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities = []
    for name in entity_names_from_snapshots(snapshots, "lead_anchor"):
        if name in DEPARTED_ANCHOR_NAMES:
            continue
        metrics = range_lead_metrics(all_snapshots, snapshots, source_table="lead_anchor", scope_name=name)
        if not has_any_metric(metrics, LEAD_ACCOUNT_CORE_METRIC_KEYS):
            continue
        latest_metrics = latest_entity_metrics(snapshots, source_table="lead_anchor", scope_name=name)
        entities.append(
            {
                "name": name,
                "anchor_name": name,
                "parent_scope": first_metric(latest_metrics).get("parent_scope", ""),
                "sort_order": metric_number(latest_metrics, "mtd_unique_leads", field="sort_order") or 0,
                "metrics": lead_metrics_for_trend(metrics),
                "daily_trends": {
                    "leads": trend_points(snapshots, source_table="lead_anchor", scope_name=name, metric_key="mtd_unique_leads"),
                    "deals": trend_points(snapshots, source_table="lead_anchor", scope_name=name, metric_key="mtd_deals"),
                },
            }
        )
    return sorted(entities, key=lambda item: (-(item["metrics"].get("leads", {}).get("actual") or 0), item["sort_order"]))


def seed_entity_payload(
    *,
    name: str,
    metrics: dict[str, dict[str, str]],
    snapshots: list[dict[str, Any]],
    source_table: str,
    entity_type: str,
    display_type: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "type": entity_type,
        "display_type": display_type,
        "parent_scope": first_metric(metrics).get("parent_scope", ""),
        "sort_order": metric_number(metrics, "mtd_impressions", field="sort_order") or 0,
        "metrics": {
            "impressions": business_metric_payload(metrics, "mtd_impressions", "impressions", "累计曝光"),
            "daily_impressions": business_metric_payload(metrics, "daily_impressions", "daily_impressions", "当日曝光"),
            "latest_impressions": business_metric_payload(metrics, "daily_impressions", "latest_impressions", "最新曝光"),
        },
        "daily_trends": {
            "impressions": canonical_trend_points(snapshots, source_table=source_table, scope_name=name, metric_key="mtd_impressions"),
        },
    }


def canonical_trend_points(
    snapshots: list[dict[str, Any]],
    *,
    source_table: str,
    scope_name: str,
    metric_key: str,
) -> list[dict[str, Any]]:
    points = []
    for snapshot in snapshots:
        metrics = canonical_metrics_for(snapshot["rows"], source_table=source_table, scope_name=scope_name)
        points.append({"date": snapshot["report_date"], "value": metric_number(metrics, metric_key)})
    return points


def trend_seed_exposure_summary(all_snapshots: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    accounts = [
        seed_entity_payload(
            name=name,
            metrics=range_seed_metrics(all_snapshots, snapshots, source_table="seed_account", scope_name=name),
            snapshots=snapshots,
            source_table="seed_account",
            entity_type="account",
            display_type="账号总曝光",
        )
        for name in canonical_entity_names_from_snapshots(snapshots, "seed_account")
    ]
    anchors = [
        seed_entity_payload(
            name=name,
            metrics=range_seed_metrics(all_snapshots, snapshots, source_table="seed_anchor", scope_name=name),
            snapshots=snapshots,
            source_table="seed_anchor",
            entity_type="anchor",
            display_type="主播曝光",
        )
        for name in canonical_entity_names_from_snapshots(snapshots, "seed_anchor")
        if name not in DEPARTED_ANCHOR_NAMES
    ]
    return {
        "accounts": sorted(accounts, key=lambda item: -(item["metrics"].get("impressions", {}).get("actual") or 0)),
        "anchors": sorted(anchors, key=lambda item: -(item["metrics"].get("impressions", {}).get("actual") or 0)),
    }


def monthly_comparison_rows(daily_trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    months = sorted(
        {
            point["date"][:7]
            for trend in daily_trends
            for point in trend.get("points", [])
            if point.get("date")
        }
    )
    rows = []
    for month in months:
        metrics = {}
        for trend in daily_trends:
            values = [
                point["value"]
                for point in trend.get("points", [])
                if point.get("date", "").startswith(month) and point.get("value") is not None
            ]
            metrics[trend["key"]] = {
                "key": trend["key"],
                "label": trend["label"],
                "unit": trend["unit"],
                "value": values[-1] if values else None,
                "coverage_days": len(values),
            }
        rows.append({"month": month, "label": month, "coverage_days": max((metric["coverage_days"] for metric in metrics.values()), default=0), "metrics": metrics})
    return rows


def normalize_unit(unit: str) -> str:
    return "人次" if unit == "次" else unit


def public_source_path(path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def metrics_for(rows: list[dict[str, str]], *, source_table: str, scope_name: str) -> dict[str, dict[str, str]]:
    return {
        row["metric_key"]: row
        for row in rows
        if row.get("source_table") == source_table and row.get("scope_name") == scope_name and row.get("metric_key")
    }


def business_summary_metrics(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    metrics = dict(metrics_for(rows, source_table="topline", scope_name="全量"))
    summary = metrics_for(rows, source_table="lead_account", scope_name="线索组汇总")
    for key in BUSINESS_SUMMARY_METRIC_KEYS:
        if key in summary:
            metrics[key] = summary[key]
    return metrics


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


def has_any_metric(metrics: dict[str, dict[str, str]], keys: set[str]) -> bool:
    return any(key in metrics and parse_number(metrics.get(key, {}).get("actual", "")) is not None for key in keys)


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
