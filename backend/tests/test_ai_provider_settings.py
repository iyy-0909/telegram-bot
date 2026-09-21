import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import crud_settings
from db.models import SystemSetting


class AiProviderSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "ai-settings.db"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        SystemSetting.__table__.create(bind=self.engine)
        self.patches = [
            patch.object(crud_settings, "SessionLocal", self.session_local),
            patch.object(crud_settings, "get_default_ai_rewrite_prompt", return_value="test prompt"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_default_provider_is_persisted_without_exposing_api_key(self):
        initial = crud_settings.get_ai_settings(owner_user_id=7)
        self.assertEqual(initial["default_provider"], "grok")

        updated = crud_settings.update_ai_settings(
            {
                "default_provider": "deepseek",
                "deepseek_api_key": "secret-key",
                "deepseek_model": "deepseek-chat",
            },
            owner_user_id=7,
        )

        self.assertEqual(updated["default_provider"], "deepseek")
        self.assertTrue(updated["providers"]["deepseek"]["configured"])
        self.assertEqual(updated["providers"]["deepseek"]["model"], "deepseek-chat")
        self.assertNotIn("secret-key", str(updated))

    def test_invalid_default_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不支持的 AI 供应商"):
            crud_settings.update_ai_settings(
                {"default_provider": "unknown"},
                owner_user_id=7,
            )

        self.assertEqual(
            crud_settings.get_default_ai_provider(owner_user_id=7),
            "grok",
        )


if __name__ == "__main__":
    unittest.main()
