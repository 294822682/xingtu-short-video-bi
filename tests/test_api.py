import unittest
from tempfile import NamedTemporaryFile

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app


class ApiTest(unittest.TestCase):
    def test_overview_contract_contains_confirmed_kpis(self):
        client = TestClient(app)

        response = client.get("/api/short-video/overview")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("overview", payload)
        self.assertIn("account_metrics", payload)
        self.assertIn("actor_metrics", payload)
        self.assertIn("video_rankings", payload)
        self.assertIn("quality_report", payload)
        self.assertEqual(payload["overview"]["total_video_count"], 320)
        self.assertEqual(payload["overview"]["total_exposure"], 12226000)
        self.assertIn("video_title", payload["video_rankings"]["top"])
        self.assertIn("video_title", payload["video_rankings"]["bottom"])

    def test_upload_endpoint_accepts_excel_file(self):
        client = TestClient(app)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "抖音测试账号"
        sheet.append(["视频名称", "发布时间", "播放量", "5s完播率", "视频演员"])
        sheet.append(["测试视频", "2026/3/1", 1000, 0.2, "桂婕、曹嘉洋"])

        with NamedTemporaryFile(suffix=".xlsx") as tmp:
            workbook.save(tmp.name)
            tmp.seek(0)
            response = client.post(
                "/api/admin/upload",
                files={"file": ("sample_short_video.xlsx", tmp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertGreaterEqual(payload["overview"]["total_video_count"], 1)


if __name__ == "__main__":
    unittest.main()
