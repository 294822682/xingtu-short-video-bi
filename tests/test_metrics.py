import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from app.metrics import (
    build_dataset_from_workbook,
    build_account_metrics,
    build_actor_metrics,
    build_overview,
    build_video_rankings,
    normalize_records,
    quality_status,
    split_actors,
)


class MetricsTest(unittest.TestCase):
    def test_video_account_completion_rate_is_missing_without_5s_field(self):
        rows = [
            {
                "source_sheet": "视频号测试",
                "headers": ["视频描述", "发布时间", "完播率", "播放量", "视频演员"],
                "values": ["测试视频", "2026/3/1", "30%", "1000", "桂婕"],
            }
        ]

        records, quality = normalize_records(rows)

        self.assertIsNone(records[0]["completion_rate"])
        self.assertEqual(records[0]["completion_metric_type"], "未提供")
        self.assertEqual(quality["missing_fields"]["视频号测试"], ["5S完播率"])

    def test_actor_split_and_exposure_are_not_shared(self):
        records = [
            {
                "platform": "抖音",
                "account_name": "抖音A",
                "exposure": 1000,
                "completion_rate": 0.2,
                "completion_metric_type": "5S完播率",
                "actors": split_actors("桂婕、曹嘉洋"),
            }
        ]

        actors = {row["actor_name"]: row for row in build_actor_metrics(records)}

        self.assertEqual(actors["桂婕"]["contributed_exposure"], 1000)
        self.assertEqual(actors["曹嘉洋"]["contributed_exposure"], 1000)

    def test_overview_uses_only_available_5s_rates(self):
        records = [
            {
                "platform": "抖音",
                "account_name": "抖音A",
                "exposure": 100,
                "completion_rate": 0.2,
                "completion_metric_type": "5S完播率",
                "actors": ["桂婕"],
            },
            {
                "platform": "视频号",
                "account_name": "视频号B",
                "exposure": 900,
                "completion_rate": None,
                "completion_metric_type": "未提供",
                "actors": [],
            },
        ]

        overview = build_overview(records, build_actor_metrics(records))

        self.assertEqual(overview["overall_5s_completion_rate"], 0.2)
        self.assertEqual(overview["overall_5s_completion_rate_display"], "20.0%")

    def test_account_metrics_include_missing_5s_display(self):
        records = [
            {
                "platform": "视频号",
                "account_name": "视频号B",
                "exposure": 900,
                "completion_rate": None,
                "completion_metric_type": "未提供",
                "actors": [],
            }
        ]

        accounts = build_account_metrics(records)

        self.assertEqual(accounts[0]["completion_5s_display"], "未提供")
        self.assertEqual(accounts[0]["completion_field_source"], "未提供")

    def test_workbook_dataset_prefers_univer_visible_rows(self):
        openpyxl_rows = [
            {
                "source_sheet": "抖音A",
                "headers": ["视频名称", "发布时间", "播放量", "5S完播率", "视频演员"],
                "values": ["openpyxl行", "2026/3/1", "1", "10%", ""],
            }
        ]
        univer_rows = [
            {
                "source_sheet": "抖音A",
                "headers": ["视频名称", "发布时间", "播放量", "5S完播率", "视频演员"],
                "values": ["univer行", "2026/3/1", "100", "20%", "桂婕"],
            },
            {
                "source_sheet": "抖音A",
                "headers": ["视频名称", "发布时间", "播放量", "5S完播率", "视频演员"],
                "values": ["univer行2", "2026/3/2", "200", "30%", ""],
            },
        ]

        with patch("app.metrics.rows_from_univer", return_value=univer_rows), patch(
            "app.metrics.rows_from_openpyxl", return_value=openpyxl_rows
        ):
            dataset = build_dataset_from_workbook(Path("placeholder.xlsx"), "placeholder.xlsx")

        self.assertEqual(dataset["overview"]["total_video_count"], 2)
        self.assertEqual(dataset["overview"]["total_exposure"], 300)
        self.assertEqual(dataset["overview"]["actor_video_count"], 1)

    def test_univer_command_retries_replay_timeout(self):
        import app.metrics as metrics

        timeout_result = subprocess.CompletedProcess(
            ["univer"],
            1,
            stdout="",
            stderr="session.loadWorkbookDataReplayPack timeout",
        )
        success_result = subprocess.CompletedProcess(["univer"], 0, stdout="ok", stderr="")

        with patch("app.metrics.subprocess.run", side_effect=[timeout_result, success_result]) as run, patch(
            "app.metrics.time.sleep"
        ):
            result = metrics.run_univer_command(["univer", "inspect"], retries=1)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok")
        self.assertEqual(run.call_count, 2)

    def test_dataset_keeps_empty_detail_sheet_accounts_visible(self):
        rows = [
            {
                "source_sheet": "视频号星际领航员",
                "headers": ["视频描述", "发布时间", "播放量", "视频演员"],
                "values": ["测试视频", "2026/3/1", "1000", "桂婕"],
            }
        ]

        with patch("app.metrics.rows_from_univer", return_value=rows), patch("app.metrics.rows_from_openpyxl", return_value=[]):
            dataset = build_dataset_from_workbook(Path("placeholder.xlsx"), "placeholder.xlsx")

        accounts = {row["account_name"]: row for row in dataset["account_metrics"]}
        self.assertEqual(accounts["视频号星空拍车show"]["video_count"], 0)
        self.assertEqual(accounts["视频号星空拍车show"]["completion_field_source"], "无有效视频行")
        self.assertEqual(dataset["quality_report"]["missing_fields"]["视频号星空拍车show"], ["5S完播率"])
        self.assertIn("无有效视频行", dataset["quality_report"]["sheet_issues"]["视频号星空拍车show"])

    def test_quality_status_prioritizes_missing_5s_sheet_count(self):
        status = quality_status(
            {
                "missing_fields": {"视频号A": ["5S完播率"], "视频号B": ["5S完播率"]},
                "sheet_issues": {"视频号B": ["无有效视频行"]},
                "sheets_without_5s_completion": ["视频号A", "视频号B"],
            }
        )

        self.assertEqual(status, "2 个 sheet 缺少 5S")

    def test_video_rankings_use_specific_video_titles(self):
        records = [
            {
                "platform": "抖音",
                "account_name": "账号A",
                "video_title": "爆款视频",
                "publish_time": "2026/3/1",
                "exposure": 120000,
                "actors": ["桂婕"],
            },
            {
                "platform": "视频号",
                "account_name": "账号B",
                "video_title": "低曝光视频",
                "publish_time": "2026/3/2",
                "exposure": 80,
                "actors": [],
            },
            {
                "platform": "抖音",
                "account_name": "账号C",
                "video_title": "",
                "publish_time": "2026/3/3",
                "exposure": 1,
                "actors": [],
            },
        ]

        rankings = build_video_rankings(records)

        self.assertEqual(rankings["top"]["video_title"], "爆款视频")
        self.assertEqual(rankings["top"]["account_name"], "账号A")
        self.assertEqual(rankings["bottom"]["video_title"], "低曝光视频")
        self.assertEqual(rankings["bottom"]["account_name"], "账号B")


if __name__ == "__main__":
    unittest.main()
