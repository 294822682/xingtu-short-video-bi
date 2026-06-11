import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.oae_dashboard import load_oae_dataset_from_sources
from app.oae_dashboard import load_oae_daily_dashboard_payload, load_oae_trends_payload


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
        row(report_date, "lead_account", "account", "测试账号", "mtd_deals", "累计实销", deals, 100, 0.12, "台", 1004),
        row(report_date, "lead_anchor", "anchor", "测试主播", "mtd_unique_leads", "累计唯一线索", 8, 0, "", "条", 5002, parent_scope="测试账号"),
        row(report_date, "seed_account", "account", "EXEED星途", "daily_impressions", "当日曝光", 1000, 2000, 0.5, "人次", 701),
        row(report_date, "seed_account", "account", "EXEED星途", "mtd_impressions", "累计曝光", impressions, 25000000, 0.3, "人次", 702),
        row(report_date, "seed_anchor", "anchor", "测试主播", "mtd_impressions", "累计曝光", 900, 2000, 0.45, "人次", 3002, parent_scope="EXEED星途"),
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
        self.assertEqual(payload["lead_anchors"][0]["name"], "测试主播")
        self.assertIn("metrics", payload["lead_anchors"][0])
        self.assertEqual(payload["seed_account"]["key"], "mtd_impressions")
        self.assertIn("daily-bi-trends", payload["interactions"]["module_anchors"])

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

    def test_returns_none_when_source_dir_has_no_dashboard_source(self):
        with TemporaryDirectory() as tmp:
            dataset = load_oae_dataset_from_sources(Path(tmp))

        self.assertIsNone(dataset)


if __name__ == "__main__":
    unittest.main()
