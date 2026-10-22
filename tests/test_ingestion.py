import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.ingestion import download_dataset as ingestion


class IngestionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.bronze = Path(folder.name)
        self.path_patch = patch.object(ingestion, "BRONZE_PATH", self.bronze)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.dotenv_patch = patch.object(ingestion, "load_dotenv")
        self.dotenv_patch.start()
        self.addCleanup(self.dotenv_patch.stop)

    def prepare_files(self):
        for name in ingestion.REQUIRED_FILES:
            (self.bronze / name).write_text("nonempty fixture")

    def test_cached_snapshot_does_not_require_token_or_download(self):
        self.prepare_files()
        with patch.dict(os.environ, {}, clear=True), patch.object(ingestion.kagglehub, "dataset_download") as download:
            self.assertEqual(ingestion.download_dataset(), self.bronze)
        download.assert_not_called()

    def test_missing_token_fails_before_network_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(ingestion.kagglehub, "dataset_download") as download:
            with self.assertRaisesRegex(RuntimeError, "KAGGLE_API_TOKEN"):
                ingestion.download_dataset()
        download.assert_not_called()

    def test_download_failure_propagates_to_orchestrator(self):
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "fixture"}, clear=True), patch.object(
            ingestion.kagglehub, "dataset_download", side_effect=RuntimeError("network unavailable")
        ):
            with self.assertRaisesRegex(RuntimeError, "network unavailable"):
                ingestion.download_dataset()

    def test_force_download_refreshes_existing_snapshot(self):
        self.prepare_files()
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "fixture"}, clear=True), patch.object(
            ingestion.kagglehub, "dataset_download"
        ) as download:
            ingestion.download_dataset(force_download=True)
        self.assertTrue(download.call_args.kwargs["force_download"])

    def test_missing_files_after_download_fail_validation(self):
        with patch.dict(os.environ, {"KAGGLE_API_TOKEN": "fixture"}, clear=True), patch.object(
            ingestion.kagglehub, "dataset_download"
        ):
            with self.assertRaisesRegex(RuntimeError, "required nonempty"):
                ingestion.download_dataset()


if __name__ == "__main__":
    unittest.main()
