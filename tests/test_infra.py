"""infra 层冒烟测试。运行: python -m unittest tests.test_infra -v"""
from __future__ import annotations

import logging
import unittest

from app.infra.config import load_config
from app.infra.default_config import DEFAULT_CONFIG
from app.infra.logger import get_logger, init_logger
from app.infra.paths import LOG_DIR, PROJECT_ROOT, ensure_runtime_dirs, resolve_dir


class TestPaths(unittest.TestCase):
    def test_project_root_contains_app(self) -> None:
        self.assertTrue((PROJECT_ROOT / "app").is_dir())

    def test_ensure_runtime_dirs(self) -> None:
        ensure_runtime_dirs()
        self.assertTrue(LOG_DIR.is_dir())

    def test_resolve_dir_creates_directory(self) -> None:
        target = resolve_dir("temp/_test_resolve")
        self.assertTrue(target.is_absolute())
        self.assertTrue(target.is_dir())
        target.rmdir()


class TestConfig(unittest.TestCase):
    def test_default_config_has_required_sections(self) -> None:
        for section in ("app", "capture", "recording", "audio", "export", "scrollshot", "paths"):
            self.assertIn(section, DEFAULT_CONFIG)

    def test_load_config_returns_merged_dict(self) -> None:
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("name", config["app"])
        self.assertIsInstance(config["capture"]["default_fps"], int)

    def test_load_config_missing_file_falls_back(self) -> None:
        config = load_config("config/_not_exists.yaml")
        self.assertEqual(config["app"]["name"], DEFAULT_CONFIG["app"]["name"])


class TestLogger(unittest.TestCase):
    def test_init_logger_writes_file(self) -> None:
        logger = init_logger(level=logging.INFO)
        logger.info("infra logger smoke test")
        for handler in logger.handlers:
            handler.flush()
        log_file = LOG_DIR / "app.log"
        self.assertTrue(log_file.is_file())
        self.assertIn("infra logger smoke test", log_file.read_text(encoding="utf-8"))

    def test_init_logger_is_idempotent(self) -> None:
        init_logger()
        first = len(get_logger().handlers)
        init_logger()
        self.assertEqual(len(get_logger().handlers), first)


if __name__ == "__main__":
    unittest.main(verbosity=2)