import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from app.storage import load_dataset, save_dataset


class StorageTest(unittest.TestCase):
    def test_load_dataset_uses_default_when_file_is_missing(self):
        with TemporaryDirectory() as tmp:
            dataset = load_dataset(Path(tmp) / "missing.json")

        self.assertEqual(dataset["overview"]["total_video_count"], 320)
        self.assertEqual(dataset["overview"]["total_exposure"], 12226000)

    def test_save_and_load_dataset_round_trip_keeps_chinese_values(self):
        dataset = {
            "overview": {"source_file_name": "测试文件.xlsx", "total_exposure": 12226000},
            "account_metrics": [],
            "actor_metrics": [],
            "video_rankings": {"top": None, "bottom": None},
        }

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            save_dataset(dataset, path)
            loaded = load_dataset(path)

        self.assertEqual(loaded["overview"]["source_file_name"], "测试文件.xlsx")
        self.assertEqual(loaded["overview"]["total_exposure"], 12226000)


if __name__ == "__main__":
    unittest.main()
