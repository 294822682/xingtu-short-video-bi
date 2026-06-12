import csv
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.oae_dashboard import load_oae_dataset_from_sources
from app.oae_dashboard import load_oae_daily_dashboard_payload, load_oae_trends_payload
from app.oae_dashboard import resolve_oae_source_dir


FIELDNAMES = [
    "report_date",
    "source_table",
    "scope_type",
    "scope_name",
    "parent_scope",
    "metric_key",
    "metric_name",
    "actual",
    "target",
    "attain_rate",
    "unit",
    "source_column",
    "sort_order",
]
HTML_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "app" / "oae_feishu_dashboard_interactive_html.py"


def write_source(path: Path, report_date: str, impressions: int, leads: int, deals: int) -> None:
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", impressions, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "累计唯一线索", leads, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_douyin_laike_orders", "抖音-来客线索", 12, 1000, 0.012, "条", 25),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", deals, 100, 0.12, "台", 30),
        row(report_date, "topline", "department", "全量", "mtd_spend", "累计线索费用", 1234.5, "", "", "元", 40),
        row(report_date, "topline", "department", "全量", "mtd_cpl", "总体 CPL", 56.7, 0, "", "元/条", 50),
        row(report_date, "topline", "department", "全量", "mtd_cps", "总体 CPS", 789.1, 1500, "", "元/台", 60),
        row(report_date, "topline", "department", "全量", "pending_cumulative", "待交车（累计）", 2, "", "", "台", 80),
        row(report_date, "lead_account", "account", "测试账号", "daily_leads", "当日线索", 3, 0, "", "条", 1001),
        row(report_date, "lead_account", "account", "测试账号", "mtd_unique_leads", "累计唯一线索", leads, 0, "", "条", 1002),
        row(report_date, "lead_account", "account", "测试账号", "visits", "到店数", 4, "", "", "条", 1003),
        row(report_date, "lead_account", "account", "测试账号", "visit_rate", "到店率", 0.2, "", "", "比例", 1004),
        row(report_date, "lead_account", "account", "测试账号", "visit_deal_rate", "到店成交率", 0.5, "", "", "比例", 1005),
        row(report_date, "lead_account", "account", "测试账号", "mtd_deals", "累计实销", deals, 100, 0.12, "台", 1004),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_unique_leads", "累计唯一线索", 8, 0, "", "条", 5002, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "visits", "到店数", 2, "", "", "条", 5003, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "visit_rate", "到店率", 0.25, "", "", "比例", 5004, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "visit_deal_rate", "到店成交率", 1, "", "", "比例", 5005, parent_scope="测试账号"),
        row(report_date, "seed_account", "account", "EXEED星途", "daily_impressions", "当日曝光", 1000, 2000, 0.5, "人次", 701),
        row(report_date, "seed_account", "account", "EXEED星途", "mtd_impressions", "累计曝光", impressions, 25000000, 0.3, "人次", 702),
        row(report_date, "seed_anchor", "anchor", "测试主播", "mtd_impressions", "累计曝光", 900, 2000, 0.45, "人次", 3002, parent_scope="EXEED星途"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_source_without_visits(path: Path, report_date: str, impressions: int, leads: int, deals: int) -> None:
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", impressions, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "累计唯一线索", leads, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_douyin_laike_orders", "抖音-来客线索", 12, 1000, 0.012, "条", 25),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", deals, 100, 0.12, "台", 30),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_unique_leads", "累计唯一线索", 8, 0, "", "条", 5002, parent_scope="测试账号"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_source_with_visit_only_account(path: Path, report_date: str) -> None:
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", 2000, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "累计唯一线索", 20, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_douyin_laike_orders", "抖音-来客线索", 12, 1000, 0.012, "条", 25),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", 2, 100, 0.12, "台", 30),
        row(report_date, "lead_account", "account", "测试账号", "mtd_unique_leads", "累计唯一线索", 20, 0, "", "条", 1002),
        row(report_date, "lead_account", "account", "测试账号", "mtd_deals", "累计实销", 2, 100, 0.12, "台", 1003),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_unique_leads", "累计唯一线索", 20, 0, "", "条", 1102),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_deals", "累计实销", 2, 100, 0.12, "台", 1103),
        row(report_date, "lead_account", "account", "线索组汇总", "visits", "到店数", 4, "", "", "条", 1104),
        row(report_date, "lead_account", "account", "线索组汇总", "visit_deals", "到店成交数", 2, "", "", "台", 1105),
        row(report_date, "lead_account", "account", "线索组汇总", "visit_rate", "到店率", 0.2, "", "", "比例", 1105),
        row(report_date, "lead_account", "account", "线索组汇总", "visit_deal_rate", "到店成交率", 0.5, "", "", "比例", 1106),
        row(report_date, "lead_account", "account", "快手-EXEED星途", "visits", "到店数", 7, "", "", "条", 1204),
        row(report_date, "lead_account", "account", "快手-EXEED星途", "visit_deals", "到店成交数", 1, "", "", "台", 1205),
        row(report_date, "lead_account", "account", "快手-EXEED星途", "visit_rate", "到店率", 0.1, "", "", "比例", 1205),
        row(report_date, "lead_account", "account", "快手-EXEED星途", "visit_deal_rate", "到店成交率", 0.2, "", "", "比例", 1206),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_source_with_conflicting_topline_and_summary(path: Path, report_date: str) -> None:
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", 101461500, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "累计唯一线索", 23, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_douyin_laike_orders", "抖音-来客线索", 1639, 1000, 0.012, "条", 25),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", 0, 100, 0.12, "台", 30),
        row(report_date, "topline", "department", "全量", "mtd_spend", "累计线索费用", 1823952.46, "", "", "元", 40),
        row(report_date, "topline", "department", "全量", "mtd_cpl", "总体 CPL", 80023.4482608696, 0, "", "元/条", 50),
        row(report_date, "topline", "department", "全量", "mtd_cps", "总体 CPS", 0, 1500, "", "元/台", 60),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_unique_leads", "风车线索（去重）", 35510, 0, "", "条", 1002),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_douyin_laike_orders", "抖音来客订单（去重）", 1639, 0, "", "条", 1003),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_deals", "累计实销", 29, 100, 0.12, "台", 1004),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_spend", "累计线索费用", 1823952.46, "", "", "元", 1005),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_cpl", "实际 CPL", 51.36, 0, "", "元/条", 1006),
        row(report_date, "lead_account", "account", "线索组汇总", "mtd_cps", "实际 CPS", 62894.91, 1500, "", "元/台", 1007),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_source_with_zero_visit_denominator(path: Path, report_date: str) -> None:
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", 2000, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "累计唯一线索", 20, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", 2, 100, 0.12, "台", 30),
        row(report_date, "lead_account", "account", "测试账号", "mtd_unique_leads", "风车线索（去重）", 20, 0, "", "条", 1002),
        row(report_date, "lead_account", "account", "测试账号", "mtd_deals", "累计实销", 0, 100, 0.12, "台", 1003),
        row(report_date, "lead_account", "account", "测试账号", "visits", "到店数", 0, "", "", "条", 1004),
        row(report_date, "lead_account", "account", "测试账号", "visit_rate", "到店率", 0, "", "", "比例", 1005),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_source_with_range_entities(
    path: Path,
    report_date: str,
    *,
    account_leads: int,
    account_orders: int,
    account_deals: int,
    account_spend: float,
    account_visits: int,
    anchor_leads: int,
    departed_leads: int,
    account_visit_deals: int | None = None,
    seed_account_name: str = "EXEED星途",
    seed_impressions: int = 900,
    seed_daily_impressions: int = 90,
    seed_anchor_name: str = "测试种草主播",
    seed_anchor_impressions: int = 100,
    seed_anchor_daily_impressions: int = 10,
) -> None:
    if account_visit_deals is None:
        account_visit_deals = min(account_deals, account_visits)
    rows = [
        row(report_date, "topline", "department", "全量", "impressions", "曝光", 2000, 25000000, 0.3, "次", 10),
        row(report_date, "topline", "department", "全量", "mtd_unique_leads", "风车线索（去重）", account_leads, 0, "", "条", 20),
        row(report_date, "topline", "department", "全量", "mtd_douyin_laike_orders", "抖音来客订单（去重）", account_orders, 1000, 0.012, "条", 25),
        row(report_date, "topline", "department", "全量", "mtd_deals", "累计实销", account_deals, 100, 0.12, "台", 30),
        row(report_date, "topline", "department", "全量", "mtd_spend", "累计线索费用", account_spend, "", "", "元", 40),
        row(report_date, "lead_account", "account", "测试账号", "mtd_unique_leads", "风车线索（去重）", account_leads, 0, "", "条", 1002),
        row(report_date, "lead_account", "account", "测试账号", "mtd_douyin_laike_orders", "抖音来客订单（去重）", account_orders, 0, "", "条", 1003),
        row(report_date, "lead_account", "account", "测试账号", "mtd_deals", "累计实销", account_deals, 100, 0.12, "台", 1004),
        row(report_date, "lead_account", "account", "测试账号", "mtd_spend", "累计线索费用", account_spend, "", "", "元", 1005),
        row(report_date, "lead_account", "account", "测试账号", "visits", "到店数", account_visits, "", "", "条", 1006),
        row(report_date, "lead_account", "account", "测试账号", "visit_deals", "到店成交数", account_visit_deals, "", "", "台", 1007),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_unique_leads", "风车线索（去重）", anchor_leads, 0, "", "条", 5002, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_douyin_laike_orders", "抖音来客订单（去重）", 3, 0, "", "条", 5003, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_deals", "累计实销", 1, 100, 0.12, "台", 5004, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_spend", "累计线索费用", 100, "", "", "元", 5005, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "王馨", "mtd_unique_leads", "风车线索（去重）", departed_leads, 0, "", "条", 5102, parent_scope="测试账号"),
        row(report_date, "lead_anchor", "anchor", "曹嘉洋", "mtd_unique_leads", "风车线索（去重）", departed_leads, 0, "", "条", 5202, parent_scope="测试账号"),
        row(report_date, "seed_account", "account", seed_account_name, "daily_impressions", "当日曝光", seed_daily_impressions, "", "", "人次", 3001),
        row(report_date, "seed_account", "account", seed_account_name, "mtd_impressions", "累计曝光", seed_impressions, 2000, 0.45, "人次", 3002),
        row(report_date, "seed_anchor", "anchor", seed_anchor_name, "daily_impressions", "当日曝光", seed_anchor_daily_impressions, "", "", "人次", 3003, parent_scope=seed_account_name),
        row(report_date, "seed_anchor", "anchor", seed_anchor_name, "mtd_impressions", "累计曝光", seed_anchor_impressions, 2000, 0.05, "人次", 3004, parent_scope=seed_account_name),
        row(report_date, "seed_anchor", "anchor", "曹嘉洋", "mtd_impressions", "累计曝光", 100, 2000, 0.05, "人次", 3005, parent_scope=seed_account_name),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def row(
    report_date: str,
    source_table: str,
    scope_type: str,
    scope_name: str,
    metric_key: str,
    metric_name: str,
    actual,
    target,
    attain_rate,
    unit: str,
    sort_order: int,
    *,
    parent_scope: str = "",
) -> dict[str, object]:
    return {
        "report_date": report_date,
        "source_table": source_table,
        "scope_type": scope_type,
        "scope_name": scope_name,
        "parent_scope": parent_scope,
        "metric_key": metric_key,
        "metric_name": metric_name,
        "actual": actual,
        "target": target,
        "attain_rate": attain_rate,
        "unit": unit,
        "source_column": "test",
        "sort_order": sort_order,
    }


class OaeDashboardTest(unittest.TestCase):
    def test_loads_latest_dashboard_source_as_ready_dataset(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-06-07.tsv", "2026-06-07", 1000, 10, 1)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08", 2000, 20, 2)

            dataset = load_oae_dataset_from_sources(source_dir)

        self.assertIsNotNone(dataset)
        assert dataset is not None
        self.assertEqual(dataset["overview"]["module_status"], "ready")
        self.assertEqual(dataset["overview"]["report_date"], "2026-06-08")
        self.assertEqual(dataset["overview"]["total_exposure"], 2000.0)
        self.assertEqual(dataset["overview"]["total_video_count"], 20)
        self.assertEqual(dataset["oae_dashboard"]["available_report_dates"], ["2026-06-07", "2026-06-08"])
        self.assertEqual(dataset["oae_dashboard"]["lead_accounts"][0]["account_name"], "测试账号")
        self.assertEqual(dataset["oae_dashboard"]["trends"][-1]["mtd_deals"], 2.0)

    def test_builds_original_oae_dashboard_payload_shape(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08", 2000, 20, 2)

            payload = load_oae_daily_dashboard_payload("latest", source_dir)

        self.assertEqual(payload["report_date"], "2026-06-08")
        self.assertEqual(payload["source"]["type"], "feishu_dashboard_source_tsv")
        self.assertIn("raw_leads", payload["overview"])
        self.assertEqual(payload["overview"]["impressions"]["actual"], 2000)
        self.assertEqual(payload["funnel"][0]["label"], "曝光")
        self.assertTrue(payload["account_summary"])
        self.assertEqual(payload["account_summary"][0]["name"], "测试账号")
        self.assertIn("到店", payload["account_summary"][0]["metric_groups"])
        self.assertEqual(payload["account_summary"][0]["metrics"]["visits"]["actual"], 4.0)
        self.assertEqual(payload["lead_anchors"][0]["name"], "测试主播")
        self.assertIn("metrics", payload["lead_anchors"][0])
        self.assertEqual(payload["lead_anchors"][0]["metrics"]["visits"]["actual"], 2.0)
        self.assertEqual(payload["lead_anchors"][0]["metric_groups"]["到店"]["visit_rate"]["actual"], 0.25)
        self.assertEqual(payload["seed_account"]["key"], "mtd_impressions")
        self.assertIn("daily-bi-trends", payload["interactions"]["module_anchors"])

    def test_missing_visit_fields_are_not_backfilled_as_zero(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_without_visits(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08", 2000, 20, 2)

            payload = load_oae_daily_dashboard_payload("latest", source_dir)

        anchor_metrics = payload["lead_anchors"][0]["metrics"]
        self.assertIsNone(anchor_metrics["visits"]["actual"])
        self.assertEqual(anchor_metrics["visits"]["source_status"], "not_connected")
        self.assertNotIn("到店", payload["lead_anchors"][0]["metric_groups"])

    def test_missing_core_entity_metrics_are_not_backfilled_as_zero(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_without_visits(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08", 2000, 20, 2)

            payload = load_oae_daily_dashboard_payload("latest", source_dir)

        anchor_metrics = payload["lead_anchors"][0]["metrics"]
        self.assertIsNone(anchor_metrics["daily_leads"]["actual"])
        self.assertEqual(anchor_metrics["daily_leads"]["source_status"], "not_connected")

    def test_builds_original_oae_trends_payload_shape(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-06-07.tsv", "2026-06-07", 1000, 10, 1)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08", 2000, 20, 2)

            payload = load_oae_trends_payload(end_date="2026-06-08", source_dir=source_dir)

        self.assertEqual(payload["date_range"]["end"], "2026-06-08")
        self.assertEqual(payload["daily_trends"][0]["key"], "impressions")
        self.assertEqual(payload["daily_trends"][0]["points"][-1]["value"], 2000)
        self.assertEqual(payload["core_kpi_summary"][0]["key"], "impressions")
        self.assertTrue(payload["monthly_comparison"])
        self.assertIn("impressions", payload["monthly_comparison"][0]["metrics"])
        self.assertEqual(payload["monthly_comparison"][0]["metrics"]["impressions"]["label"], "曝光")
        self.assertTrue(payload["account_summary"])
        self.assertEqual(payload["account_summary"][0]["name"], "测试账号")
        self.assertTrue(payload["anchor_summary"])
        self.assertEqual(payload["anchor_summary"][0]["name"], "测试主播")
        self.assertEqual(payload["seed_exposure_summary"]["accounts"][0]["name"], "EXEED星途")
        self.assertEqual(payload["seed_exposure_summary"]["anchors"][0]["name"], "测试主播")

    def test_trends_payload_keeps_full_requested_quarter_window(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            first = date(2026, 3, 1)
            for index in range(35):
                report_date = (first + timedelta(days=index)).isoformat()
                write_source(
                    source_dir / f"feishu_dashboard_source_latest_{report_date}.tsv",
                    report_date,
                    1000 + index,
                    10 + index,
                    1,
                )

            payload = load_oae_trends_payload(
                start_date="2026-03-01",
                end_date="2026-04-04",
                source_dir=source_dir,
            )

        self.assertEqual(payload["date_range"]["start"], "2026-03-01")
        self.assertEqual(payload["date_range"]["end"], "2026-04-04")
        self.assertEqual(len(payload["daily_trends"][0]["points"]), 35)
        self.assertEqual(payload["daily_trends"][0]["points"][0]["date"], "2026-03-01")
        self.assertEqual(payload["daily_trends"][0]["points"][-1]["date"], "2026-04-04")

    def test_trends_payload_keeps_summary_visits_and_ignores_visit_only_accounts(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_visit_only_account(source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv", "2026-06-08")

            payload = load_oae_trends_payload(
                start_date="2026-06-08",
                end_date="2026-06-08",
                source_dir=source_dir,
            )

        account_names = [item["name"] for item in payload["account_summary"]]
        self.assertIn("线索组汇总", account_names)
        self.assertIn("测试账号", account_names)
        self.assertNotIn("快手-EXEED星途", account_names)
        summary = next(item for item in payload["account_summary"] if item["name"] == "线索组汇总")
        self.assertEqual(summary["metrics"]["visits"]["actual"], 4.0)
        self.assertEqual(summary["metrics"]["visit_rate"]["actual"], 0.2)
        self.assertEqual(summary["metrics"]["visit_deal_rate"]["actual"], 0.5)

    def test_trends_payload_uses_deduped_windmill_and_douyin_order_summary_metrics(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_conflicting_topline_and_summary(
                source_dir / "feishu_dashboard_source_latest_2026-04-30.tsv",
                "2026-04-30",
            )

            payload = load_oae_trends_payload(
                start_date="2026-04-30",
                end_date="2026-04-30",
                source_dir=source_dir,
            )
            latest = load_oae_daily_dashboard_payload("latest", source_dir)

        month = payload["monthly_comparison"][0]
        self.assertEqual(month["metrics"]["leads"]["label"], "风车线索（去重）")
        self.assertEqual(month["metrics"]["leads"]["value"], 35510.0)
        self.assertEqual(month["metrics"]["douyin_laike_orders"]["label"], "抖音来客订单（去重）")
        self.assertEqual(month["metrics"]["douyin_laike_orders"]["value"], 1639.0)
        self.assertEqual(month["metrics"]["deals"]["value"], 29.0)
        self.assertEqual(month["metrics"]["cpl"]["value"], 51.36)
        self.assertEqual(month["metrics"]["cps"]["value"], 62894.91)
        self.assertEqual(latest["overview"]["mtd_unique_leads"]["actual"], 35510.0)
        self.assertEqual(latest["overview"]["mtd_unique_leads"]["label"], "风车线索（去重）")
        self.assertEqual(latest["overview"]["mtd_douyin_laike_orders"]["label"], "抖音来客订单（去重）")
        self.assertEqual(latest["funnel"][2]["label"], "风车线索（去重）")
        self.assertEqual(latest["funnel"][3]["label"], "抖音来客订单（去重）")

    def test_zero_visit_denominator_is_not_applicable_not_missing(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_zero_visit_denominator(
                source_dir / "feishu_dashboard_source_latest_2026-06-08.tsv",
                "2026-06-08",
            )

            payload = load_oae_trends_payload(
                start_date="2026-06-08",
                end_date="2026-06-08",
                source_dir=source_dir,
            )

        account = payload["account_summary"][0]
        visit_deal_rate = account["metrics"]["visit_deal_rate"]
        self.assertIsNone(visit_deal_rate["actual"])
        self.assertEqual(visit_deal_rate["source_status"], "not_applicable")

    def test_visit_rate_over_100_is_not_applicable(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            rows = [
                row("2026-06-10", "topline", "department", "全量", "impressions", "曝光", 2000, 25000000, 0.3, "次", 10),
                row("2026-06-10", "topline", "department", "全量", "mtd_unique_leads", "风车线索（去重）", 2, 0, "", "条", 20),
                row("2026-06-10", "topline", "department", "全量", "mtd_deals", "累计实销", 1, 100, 0.12, "台", 30),
                row("2026-06-10", "lead_account", "account", "测试账号", "mtd_unique_leads", "风车线索（去重）", 2, 0, "", "条", 1002),
                row("2026-06-10", "lead_account", "account", "测试账号", "mtd_deals", "累计实销", 1, 100, 0.12, "台", 1003),
                row("2026-06-10", "lead_account", "account", "测试账号", "visits", "到店数", 3, "", "", "条", 1004),
                row("2026-06-10", "lead_account", "account", "测试账号", "visit_rate", "到店率", 1.5, "", "", "比例", 1005),
                row("2026-06-10", "lead_account", "account", "测试账号", "visit_deal_rate", "到店成交率", 1 / 3, "", "", "比例", 1006),
            ]
            with (source_dir / "feishu_dashboard_source_latest_2026-06-10.tsv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, FIELDNAMES, delimiter="\t")
                writer.writeheader()
                writer.writerows(rows)

            latest = load_oae_daily_dashboard_payload("latest", source_dir)
            trends = load_oae_trends_payload(start_date="2026-06-10", end_date="2026-06-10", source_dir=source_dir)

        latest_visit_rate = latest["account_summary"][0]["metrics"]["visit_rate"]
        self.assertIsNone(latest_visit_rate["actual"])
        self.assertEqual(latest_visit_rate["source_status"], "not_applicable")
        self.assertEqual(latest_visit_rate["note"], "到店数大于风车线索数，无法计算到店率")

        trend_visit_rate = trends["account_summary"][0]["metrics"]["visit_rate"]
        self.assertIsNone(trend_visit_rate["actual"])
        self.assertEqual(trend_visit_rate["source_status"], "not_applicable")
        self.assertEqual(trend_visit_rate["note"], "到店数大于风车线索数，无法计算到店率")

    def test_trends_account_and_anchor_summaries_use_selected_range_not_latest_snapshot(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_range_entities(
                source_dir / "feishu_dashboard_source_latest_2026-05-31.tsv",
                "2026-05-31",
                account_leads=100,
                account_orders=30,
                account_deals=10,
                account_spend=1000,
                account_visits=20,
                anchor_leads=40,
                departed_leads=999,
                seed_account_name="抖音-EXEED星途",
                seed_impressions=1000,
                seed_daily_impressions=100,
                seed_anchor_impressions=300,
                seed_anchor_daily_impressions=30,
            )
            write_source_with_range_entities(
                source_dir / "feishu_dashboard_source_latest_2026-06-10.tsv",
                "2026-06-10",
                account_leads=20,
                account_orders=7,
                account_deals=2,
                account_spend=200,
                account_visits=5,
                anchor_leads=5,
                departed_leads=999,
                seed_account_name="EXEED星途",
                seed_impressions=500,
                seed_daily_impressions=50,
                seed_anchor_impressions=200,
                seed_anchor_daily_impressions=20,
            )

            payload = load_oae_trends_payload(
                start_date="2026-05-31",
                end_date="2026-06-10",
                source_dir=source_dir,
            )

        account = next(item for item in payload["account_summary"] if item["name"] == "测试账号")
        account_metrics = account["metrics"]
        self.assertEqual(account_metrics["leads"]["actual"], 120.0)
        self.assertEqual(account_metrics["douyin_laike_orders"]["actual"], 37.0)
        self.assertEqual(account_metrics["deals"]["actual"], 12.0)
        self.assertEqual(account_metrics["spend"]["actual"], 1200.0)
        self.assertEqual(account_metrics["visits"]["actual"], 25.0)
        self.assertAlmostEqual(account_metrics["visit_rate"]["actual"], 25 / 120)
        self.assertAlmostEqual(account_metrics["visit_deal_rate"]["actual"], 12 / 25)
        self.assertEqual(account_metrics["cpl"]["actual"], 10.0)
        self.assertEqual(account_metrics["cps"]["actual"], 100.0)

        anchor_names = [item["name"] for item in payload["anchor_summary"]]
        self.assertIn("测试主播", anchor_names)
        self.assertNotIn("王馨", anchor_names)
        self.assertNotIn("曹嘉洋", anchor_names)
        anchor = next(item for item in payload["anchor_summary"] if item["name"] == "测试主播")
        self.assertEqual(anchor["metrics"]["leads"]["actual"], 45.0)
        seed_account = next(item for item in payload["seed_exposure_summary"]["accounts"] if item["name"] == "EXEED星途")
        self.assertEqual(seed_account["metrics"]["impressions"]["actual"], 1500.0)
        self.assertEqual(seed_account["metrics"]["daily_impressions"]["actual"], 150.0)
        seed_anchor = next(item for item in payload["seed_exposure_summary"]["anchors"] if item["name"] == "测试种草主播")
        self.assertEqual(seed_anchor["metrics"]["impressions"]["actual"], 500.0)
        self.assertEqual(seed_anchor["metrics"]["daily_impressions"]["actual"], 50.0)
        seed_anchor_names = [item["name"] for item in payload["seed_exposure_summary"]["anchors"]]
        self.assertNotIn("曹嘉洋", seed_anchor_names)

    def test_range_visit_deal_rate_uses_visited_deals_not_total_deals(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_range_entities(
                source_dir / "feishu_dashboard_source_latest_2026-06-10.tsv",
                "2026-06-10",
                account_leads=100,
                account_orders=20,
                account_deals=30,
                account_spend=300,
                account_visits=5,
                account_visit_deals=2,
                anchor_leads=10,
                departed_leads=0,
            )

            payload = load_oae_trends_payload(
                start_date="2026-06-10",
                end_date="2026-06-10",
                source_dir=source_dir,
            )

        account = next(item for item in payload["account_summary"] if item["name"] == "测试账号")
        visit_deal_rate = account["metrics"]["visit_deal_rate"]
        self.assertAlmostEqual(visit_deal_rate["actual"], 2 / 5)
        self.assertEqual(visit_deal_rate["source_status"], "available")

    def test_range_visit_deal_rate_is_not_applicable_when_visited_deals_exceed_visits(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source_with_range_entities(
                source_dir / "feishu_dashboard_source_latest_2026-06-10.tsv",
                "2026-06-10",
                account_leads=100,
                account_orders=20,
                account_deals=30,
                account_spend=300,
                account_visits=5,
                account_visit_deals=6,
                anchor_leads=10,
                departed_leads=0,
            )

            payload = load_oae_trends_payload(
                start_date="2026-06-10",
                end_date="2026-06-10",
                source_dir=source_dir,
            )

        account = next(item for item in payload["account_summary"] if item["name"] == "测试账号")
        visit_deal_rate = account["metrics"]["visit_deal_rate"]
        self.assertIsNone(visit_deal_rate["actual"])
        self.assertEqual(visit_deal_rate["source_status"], "not_applicable")
        self.assertEqual(visit_deal_rate["note"], "到店成交数大于到店数，无法计算到店成交率")

    def test_business_html_formats_unit_costs_as_unit_money_not_wan(self):
        html_source = HTML_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn("function isUnitCost(unit)", html_source)
        self.assertIn("isUnitCost(unit) ? fmtMoney(value) : fmtMoneyWan(value)", html_source)
        self.assertIn("isUnitCost(unit) ? fmtMoney(numeric) : fmtMoneyWan(numeric)", html_source)
        self.assertIn("return anchor.metrics?.[key] || {{ actual: null", html_source)
        self.assertIn('item?.source_status === "not_applicable"', html_source)
        self.assertIn('metricStatusNote(item)', html_source)
        self.assertIn("accountNotApplicableSummary(entity)", html_source)
        self.assertIn("范围日曝光合计", html_source)
        self.assertNotIn("最新曝光", html_source)
        self.assertIn("风车线索（去重）", html_source)
        self.assertIn("抖音来客订单（去重）", html_source)
        self.assertNotIn("唯一线索", html_source)
        self.assertNotIn("来客线索", html_source)
        self.assertNotIn("上一周期值：未提供", html_source)
        self.assertNotIn("差值：未提供", html_source)
        self.assertNotIn("变化率：未提供", html_source)

    def test_trends_default_range_uses_calendar_three_month_window_not_last_31_snapshots(self):
        with TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            write_source(source_dir / "feishu_dashboard_source_latest_2026-04-27.tsv", "2026-04-27", 800, 8, 1)
            current = date(2026, 5, 9)
            while current <= date(2026, 6, 8):
                write_source(
                    source_dir / f"feishu_dashboard_source_latest_{current.isoformat()}.tsv",
                    current.isoformat(),
                    1000,
                    10,
                    1,
                )
                current += timedelta(days=1)

            payload = load_oae_trends_payload(source_dir=source_dir)

        self.assertEqual(payload["date_range"]["start_date"], "2026-04-01")
        self.assertEqual(payload["date_range"]["end_date"], "2026-06-08")
        self.assertEqual(payload["date_range"]["days"], 69)
        self.assertIn("2026-04-27", payload["available_dates"])
        self.assertIn("2026-04-01", payload["missing_dates"])
        self.assertEqual(payload["monthly_comparison"][0]["month"], "2026-04")
        self.assertEqual(payload["monthly_comparison"][0]["coverage_days"], 1)

    def test_returns_none_when_source_dir_has_no_dashboard_source(self):
        with TemporaryDirectory() as tmp:
            dataset = load_oae_dataset_from_sources(Path(tmp))

        self.assertIsNone(dataset)

    def test_resolve_source_dir_uses_newest_available_dashboard_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_dir = root / "runtime" / "oae" / "sql_reports"
            packaged_dir = root / "packaged" / "oae" / "sql_reports"
            runtime_dir.mkdir(parents=True)
            packaged_dir.mkdir(parents=True)
            write_source(runtime_dir / "feishu_dashboard_source_latest_2026-06-09.tsv", "2026-06-09", 1000, 10, 1)
            write_source(packaged_dir / "feishu_dashboard_source_latest_2026-06-10.tsv", "2026-06-10", 2000, 20, 2)

            with patch.dict(
                os.environ,
                {
                    "OAE_DASHBOARD_SOURCE_DIR": str(runtime_dir),
                    "BI_DATA_DIR": str(root / "packaged"),
                },
                clear=False,
            ):
                resolved = resolve_oae_source_dir()

        self.assertEqual(resolved, packaged_dir)


if __name__ == "__main__":
    unittest.main()
