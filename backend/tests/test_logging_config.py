"""Application INFO logs must reach a handler when served by uvicorn."""
import logging
import unittest
from unittest.mock import patch

from app.main import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def setUp(self):
        self.app_logger = logging.getLogger("app")
        self.previous_level = self.app_logger.level
        self.addCleanup(self.app_logger.setLevel, self.previous_level)

    def test_app_info_records_are_emitted_at_default_level(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("LOG_LEVEL", None)
            configure_logging()
        self.assertTrue(logging.getLogger().handlers, "root logger has no handler")
        self.assertTrue(logging.getLogger("app.services.shopify_sync").isEnabledFor(logging.INFO))

    def test_log_level_env_is_honoured_and_invalid_values_fall_back(self):
        with patch.dict("os.environ", {"LOG_LEVEL": "debug"}):
            configure_logging()
        self.assertEqual(self.app_logger.level, logging.DEBUG)
        with patch.dict("os.environ", {"LOG_LEVEL": "loud"}):
            configure_logging()
        self.assertEqual(self.app_logger.level, logging.INFO)

    def test_existing_host_logging_configuration_is_preserved(self):
        root = logging.getLogger()
        sentinel = logging.NullHandler()
        root.addHandler(sentinel)
        self.addCleanup(root.removeHandler, sentinel)
        before = list(root.handlers)
        with patch.dict("os.environ", {"LOG_LEVEL": "WARNING"}):
            configure_logging()
        self.assertEqual(root.handlers, before)
        self.assertEqual(self.app_logger.level, logging.WARNING)


if __name__ == "__main__":
    unittest.main()
