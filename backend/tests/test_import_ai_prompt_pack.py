import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.import_ai_prompt_pack import ImportValidationError, import_prompt_pack


class ImportAiPromptPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "app.db"
        self.pack = self.root / "pack.json"
        self.write_pack()
        self.create_database()

    def tearDown(self):
        self.temporary.cleanup()

    def write_pack(self):
        prompts = []
        names = {
            "product": "场所介绍与消费明细",
            "promotion": "优惠活动",
            "notice": "营业与预约通知",
            "tutorial": "攻略与避坑知识",
            "story": "情绪引流与团队背书",
            "general": "短视频与混合内容（兜底）",
        }
        for content_type, suffix in names.items():
            prompts.append(
                {
                    "name": f"商K｜{suffix}",
                    "content_type": content_type,
                    "content": f"{content_type} 分类规则",
                    "enabled": True,
                    "is_default": False,
                }
            )
        payload = {
            "target_username": "pack_user",
            "prompts": prompts,
            "common_rules": "多城市共同规则 {{rewrite_ratio}} {{max_chars}}",
            "default_prompt": {
                "name": "系统默认提示词",
                "content": "系统默认正文 {{content}}",
            },
        }
        self.pack.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def create_database(self, *, default_name="系统默认提示词"):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE user_accounts (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE
            );
            CREATE TABLE ai_prompt_templates (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(owner_user_id, name)
            );
            CREATE TABLE system_settings (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                remark TEXT,
                updated_at TEXT,
                UNIQUE(owner_user_id, key)
            );
            CREATE TABLE clone_tasks (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                ai_prompt_template_id INTEGER
            );
            CREATE TABLE listener_tasks (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                ai_prompt_template_id INTEGER
            );
            """
        )
        connection.execute(
            "INSERT INTO user_accounts(id, username) VALUES(1, 'a18573530930')"
        )
        connection.execute(
            "INSERT INTO ai_prompt_templates"
            "(id, owner_user_id, name, content, is_default, enabled) "
            "VALUES(1, 1, ?, '旧默认内容', 1, 1)",
            (default_name,),
        )
        connection.execute(
            "INSERT INTO ai_prompt_templates"
            "(id, owner_user_id, name, content, is_default, enabled) "
            "VALUES(4, 1, '上海频道｜场所介绍与消费明细', 'product 分类规则', 0, 1)"
        )
        connection.execute(
            "INSERT INTO clone_tasks(id, owner_user_id, ai_prompt_template_id) VALUES(11, 1, 4)"
        )
        connection.execute(
            "INSERT INTO listener_tasks(id, owner_user_id, ai_prompt_template_id) VALUES(12, 1, 4)"
        )
        connection.commit()
        connection.close()

    def test_dry_run_does_not_mutate_and_explicit_username_overrides_pack(self):
        before = self.database.read_bytes()
        result = import_prompt_pack(
            self.database,
            self.pack,
            "a18573530930",
            update_system_default=True,
        )
        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["plan"]["owner_id"], 1)
        self.assertEqual(result["plan"]["username"], "a18573530930")
        self.assertEqual(result["plan"]["schema_changes"], ["ai_prompt_templates.content_type"])
        self.assertEqual(self.database.read_bytes(), before)
        with self.assertRaises(ImportValidationError):
            import_prompt_pack(self.database, self.pack, "missing_user")

    def test_apply_preserves_bound_id_and_second_apply_is_idempotent(self):
        result = import_prompt_pack(
            self.database,
            self.pack,
            "a18573530930",
            apply=True,
            update_system_default=True,
        )
        self.assertTrue(result["verified"])
        self.assertTrue(Path(result["backup"]).is_file())

        connection = sqlite3.connect(self.database)
        try:
            row = connection.execute(
                "SELECT id, name, content_type FROM ai_prompt_templates "
                "WHERE name='商K｜场所介绍与消费明细'"
            ).fetchone()
            self.assertEqual(row, (4, "商K｜场所介绍与消费明细", "product"))
            self.assertEqual(
                connection.execute(
                    "SELECT ai_prompt_template_id FROM clone_tasks WHERE id=11"
                ).fetchone()[0],
                4,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT ai_prompt_template_id FROM listener_tasks WHERE id=12"
                ).fetchone()[0],
                4,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM ai_prompt_templates "
                    "WHERE owner_user_id=1 AND name LIKE '商K｜%'"
                ).fetchone()[0],
                6,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM system_settings "
                    "WHERE owner_user_id=1 AND key='ai_common_rewrite_rules'"
                ).fetchone()[0],
                1,
            )
            default_content = connection.execute(
                "SELECT content FROM ai_prompt_templates WHERE id=1"
            ).fetchone()[0]
            self.assertEqual(default_content, "系统默认正文 {{content}}")
        finally:
            connection.close()

        second = import_prompt_pack(
            self.database,
            self.pack,
            "a18573530930",
            apply=True,
            update_system_default=True,
        )
        self.assertTrue(second["verified"])
        self.assertFalse(second["plan"]["changed"])
        self.assertIsNone(second["backup"])

    def test_custom_default_and_new_legacy_conflict_are_rejected(self):
        self.database.unlink()
        self.create_database(default_name="我的自定义默认")
        with self.assertRaisesRegex(ImportValidationError, "自定义模板"):
            import_prompt_pack(
                self.database,
                self.pack,
                "a18573530930",
                apply=True,
                update_system_default=True,
            )

        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "INSERT INTO ai_prompt_templates"
                "(id, owner_user_id, name, content, is_default, enabled) "
                "VALUES(5, 1, '商K｜场所介绍与消费明细', '其他内容', 0, 1)"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(ImportValidationError, "同时存在新旧"):
            import_prompt_pack(self.database, self.pack, "a18573530930")

    def test_system_default_is_untouched_without_explicit_flag(self):
        result = import_prompt_pack(
            self.database,
            self.pack,
            "a18573530930",
            apply=True,
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["plan"]["system_default"]["action"], "skipped")
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT content FROM ai_prompt_templates WHERE id=1"
                ).fetchone()[0],
                "旧默认内容",
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT value FROM system_settings "
                    "WHERE owner_user_id=1 AND key='ai_default_rewrite_prompt'"
                ).fetchone()
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
