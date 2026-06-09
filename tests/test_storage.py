import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from app.storage import dataset_path_from_env, load_dataset, save_dataset


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

    def test_oae_default_dataset_is_separate_from_xingtu(self):
        dataset = load_dataset(module_slug="oae")

        self.assertEqual(dataset["overview"]["module_status"], "ready")
        self.assertEqual(dataset["overview"]["source_contract"], "feishu_dashboard_source_tsv")
        self.assertGreater(dataset["overview"]["total_exposure"], 0)

    def test_oae_falls_back_to_pending_dataset_when_source_is_missing(self):
        with patch("app.storage.load_oae_dataset_from_sources", return_value=None):
            dataset = load_dataset(module_slug="oae")

        self.assertEqual(dataset["overview"]["module_status"], "pending_source_contract")
        self.assertEqual(dataset["overview"]["total_exposure"], 0)

    def test_dataset_path_from_env_keeps_xingtu_backward_compatible(self):
        with TemporaryDirectory() as tmp:
            with unittest.mock.patch.dict("os.environ", {"XINGTU_DATA_DIR": tmp}, clear=False):
                self.assertEqual(dataset_path_from_env("xingtu"), Path(tmp) / "dataset.json")
                self.assertEqual(dataset_path_from_env("oae"), Path(tmp) / "oae_dataset.json")


if __name__ == "__main__":
    unittest.main()
