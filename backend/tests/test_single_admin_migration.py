import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SingleAdminMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "legacy.db"
        self.session_root = Path(self.temp_dir.name) / "backend" / "data" / "sessions"
        self.legacy_session_base = Path(self.temp_dir.name) / "legacy-account"
        self.legacy_session_file = self.legacy_session_base.with_suffix(".session")
        self.legacy_session_journal = Path(f"{self.legacy_session_file}-journal")
        self.legacy_session_file.write_bytes(b"legacy-session")
        self.legacy_session_journal.write_bytes(b"legacy-journal")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    session_path VARCHAR NOT NULL
                );
                CREATE TABLE clone_tasks (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    source_channel VARCHAR NOT NULL,
                    target_channels TEXT,
                    account_id INTEGER
                );
                INSERT INTO clone_tasks (
                    id, name, source_channel, target_channels, account_id
                ) VALUES (
                    11, 'legacy clone', '@source', '["@target"]', 7
                );

                CREATE TABLE system_settings (
                    id INTEGER PRIMARY KEY,
                    key VARCHAR NOT NULL UNIQUE,
                    value TEXT,
                    remark TEXT
                );
                INSERT INTO system_settings (id, key, value, remark)
                VALUES (5, 'legacy_key', 'legacy_value', 'keep me');
                """
            )
            connection.execute(
                "INSERT INTO accounts (id, name, session_path) VALUES (?, ?, ?)",
                (7, "legacy account", self.legacy_session_base.as_posix()),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_migration(self, *args):
        backend_dir = Path(__file__).resolve().parents[1]
        script = backend_dir / "scripts" / "migrate_single_admin_ownership.py"
        env = dict(os.environ)
        env["DATABASE_URL"] = f"sqlite:///{self.db_path.as_posix()}"
        env["MIGRATION_ADMIN_PASSWORD"] = "migration-test-123"
        env["TELEGRAM_SESSION_STORAGE_ROOT"] = self.session_root.as_posix()
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(backend_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def add_existing_admin_and_sessions(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE user_accounts (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(32) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    plan_tier VARCHAR(16) NOT NULL,
                    feature_keys_json TEXT NOT NULL,
                    access_expires_at DATETIME,
                    advertisement_text TEXT NOT NULL,
                    advertisement_send_time VARCHAR(5) NOT NULL,
                    failed_login_count INTEGER NOT NULL,
                    locked_until DATETIME,
                    last_login_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                INSERT INTO user_accounts VALUES (
                    1, 'owner_generated', 'old-hash', 'admin', 'active', 'paid',
                    '[]', NULL, 'ad', '12:00', 0, NULL, NULL,
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                );

                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    revoked_at DATETIME,
                    created_at DATETIME NOT NULL,
                    last_seen_at DATETIME NOT NULL
                );
                INSERT INTO user_sessions VALUES (
                    1, 1, 'token-one', '2030-01-01 00:00:00', NULL,
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                );
                INSERT INTO user_sessions VALUES (
                    2, 1, 'token-two', '2030-01-01 00:00:00', NULL,
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def latest_migration_report(self):
        reports = sorted(
            self.db_path.parent.glob("single-admin-migration-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
        )
        self.assertTrue(reports)
        return json.loads(reports[-1].read_text(encoding="utf-8"))

    def test_migration_preserves_rows_and_assigns_every_owner_to_admin(self):
        dry_run = self.run_migration(
            "--dry-run",
            "--admin-username",
            "migration_admin",
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr or dry_run.stdout)

        result = self.run_migration(
            "--execute",
            "--admin-username",
            "migration_admin",
            "--confirm",
            "SINGLE_ADMIN_OWNERSHIP",
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        connection = sqlite3.connect(self.db_path)
        try:
            admin = connection.execute(
                "SELECT id, username, role, status, plan_tier, access_expires_at "
                "FROM user_accounts"
            ).fetchone()
            self.assertEqual(admin[1:], (
                "migration_admin",
                "admin",
                "active",
                "paid",
                None,
            ))
            admin_id = admin[0]
            self.assertEqual(
                connection.execute(
                    "SELECT name, owner_user_id FROM accounts WHERE id = 7"
                ).fetchone(),
                ("legacy account", admin_id),
            )
            migrated_session_path = connection.execute(
                "SELECT session_path FROM accounts WHERE id = 7"
            ).fetchone()[0]
            self.assertEqual(
                connection.execute(
                    "SELECT name, account_id, owner_user_id FROM clone_tasks WHERE id = 11"
                ).fetchone(),
                ("legacy clone", 7, admin_id),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT value, remark, owner_user_id FROM system_settings WHERE id = 5"
                ).fetchone(),
                ("legacy_value", "keep me", admin_id),
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            unique_columns = []
            for index in connection.execute(
                "PRAGMA index_list('system_settings')"
            ).fetchall():
                if not index[2]:
                    continue
                unique_columns.append([
                    row[2]
                    for row in connection.execute(
                        f"PRAGMA index_info('{index[1]}')"
                    ).fetchall()
                ])
            self.assertIn(["owner_user_id", "key"], unique_columns)
            owned_tables = []
            for (table_name,) in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall():
                columns = connection.execute(
                    f"PRAGMA table_info('{table_name}')"
                ).fetchall()
                owner_column = next(
                    (column for column in columns if column[1] == "owner_user_id"),
                    None,
                )
                if owner_column is None:
                    continue
                owned_tables.append(table_name)
                self.assertEqual(owner_column[3], 1, table_name)
            self.assertTrue(owned_tables)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO bot_accounts (owner_user_id, name, token, enabled) "
                    "VALUES (NULL, 'invalid', 'invalid', 1)"
                )
            connection.rollback()
        finally:
            connection.close()

        self.assertTrue(list(self.db_path.parent.glob("legacy.db.bak_single_admin_*")))
        self.assertTrue(list(self.db_path.parent.glob("single-admin-migration-*.json")))
        migrated_base = Path(migrated_session_path)
        if not migrated_base.is_absolute():
            migrated_base = Path(__file__).resolve().parents[1] / migrated_base
        self.assertEqual(migrated_base.parent.resolve(), (self.session_root / f"user_{admin_id}").resolve())
        self.assertEqual(migrated_base.with_suffix(".session").read_bytes(), b"legacy-session")
        self.assertEqual(Path(f"{migrated_base.with_suffix('.session')}-journal").read_bytes(), b"legacy-journal")
        self.assertTrue(self.legacy_session_file.exists())
        self.assertTrue(self.legacy_session_journal.exists())

    def test_preexisting_orphan_reference_is_preserved_and_reported_as_baseline(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE clone_tasks SET account_id = 999 WHERE id = 11"
            )
            connection.commit()
        finally:
            connection.close()

        result = self.run_migration(
            "--execute",
            "--admin-username",
            "migration_admin",
            "--confirm",
            "SINGLE_ADMIN_OWNERSHIP",
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        report = self.latest_migration_report()
        reference_errors = report["verification"]["reference_errors"]
        key = "clone_tasks.account_id->accounts"
        self.assertEqual(reference_errors["baseline"], {key: 1})
        self.assertEqual(reference_errors["current"], {key: 1})
        self.assertEqual(reference_errors["new_or_increased"], {})
        self.assertTrue(report["verification"]["ok"])

        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT account_id FROM clone_tasks WHERE id = 11"
                ).fetchone(),
                (999,),
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM clone_tasks").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_reference_error_comparison_rejects_new_or_increased_counts(self):
        from scripts import migrate_single_admin_ownership as migration

        result = migration.compare_reference_errors(
            {
                "same": 2,
                "decreased": 3,
                "increased": 1,
            },
            {
                "same": 2,
                "decreased": 2,
                "increased": 4,
                "new": 1,
            },
        )

        self.assertEqual(
            result,
            {
                "increased": {
                    "baseline": 1,
                    "current": 4,
                    "increase": 3,
                },
                "new": {
                    "baseline": 0,
                    "current": 1,
                    "increase": 1,
                },
            },
        )

    def test_single_existing_user_is_renamed_in_place_and_sessions_are_kept_by_default(self):
        self.add_existing_admin_and_sessions()
        result = self.run_migration(
            "--execute",
            "--admin-username",
            "target_admin",
            "--confirm",
            "SINGLE_ADMIN_OWNERSHIP",
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT id, username FROM user_accounts"
                ).fetchone(),
                (1, "target_admin"),
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0],
                2,
            )
        finally:
            connection.close()

    def test_existing_sessions_are_revoked_only_with_explicit_flag(self):
        self.add_existing_admin_and_sessions()
        result = self.run_migration(
            "--execute",
            "--admin-username",
            "target_admin",
            "--confirm",
            "SINGLE_ADMIN_OWNERSHIP",
            "--revoke-existing-sessions",
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0],
                0,
            )
        finally:
            connection.close()
        self.assertIn('"revoked_session_count": 2', result.stdout)

    def test_duplicate_legacy_session_paths_are_rejected_before_copy(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "INSERT INTO accounts (id, name, session_path) VALUES (?, ?, ?)",
                (8, "duplicate", self.legacy_session_base.as_posix()),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.run_migration(
            "--dry-run",
            "--admin-username",
            "target_admin",
        )
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        self.assertIn('"duplicate_session_account_ids"', result.stdout)
        self.assertFalse((self.session_root / "user_1").exists())

    def test_legacy_support_upload_is_copied_into_owner_directory(self):
        from bot import support_media
        from scripts import migrate_single_admin_ownership as migration

        media_db = Path(self.temp_dir.name) / "support-media.db"
        media_root = Path(self.temp_dir.name) / "support-media"
        media_root.mkdir(parents=True)
        legacy_file = media_root / "legacy-welcome.jpg"
        legacy_file.write_bytes(b"legacy-support-media")

        connection = sqlite3.connect(media_db)
        try:
            connection.executescript(
                """
                CREATE TABLE support_bots (
                    id INTEGER PRIMARY KEY,
                    welcome_media_file_id TEXT
                );
                INSERT INTO support_bots VALUES (
                    8, 'support_upload:legacy-welcome.jpg'
                );
                INSERT INTO support_bots VALUES (
                    9, 'telegram-file-id'
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

        with patch.object(support_media, "SUPPORT_MEDIA_DIR", media_root):
            result = migration.migrate_support_media_refs(media_db, 17)

        connection = sqlite3.connect(media_db)
        try:
            migrated_ref = connection.execute(
                "SELECT welcome_media_file_id FROM support_bots WHERE id = 8"
            ).fetchone()[0]
            untouched_ref = connection.execute(
                "SELECT welcome_media_file_id FROM support_bots WHERE id = 9"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertTrue(migrated_ref.startswith("support_upload:v2:17:"))
        migrated_filename = migrated_ref.split(":", 3)[3]
        self.assertEqual(
            (media_root / "17" / migrated_filename).read_bytes(),
            b"legacy-support-media",
        )
        self.assertTrue(legacy_file.exists())
        self.assertEqual(untouched_ref, "telegram-file-id")
        self.assertEqual(result["migrated"], 1)
        self.assertTrue(result["legacy_files_retained"])

    def test_more_than_one_existing_user_is_rejected(self):
        self.add_existing_admin_and_sessions()
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "INSERT INTO user_accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    2,
                    "second_user",
                    "hash",
                    "user",
                    "active",
                    "free",
                    "[]",
                    None,
                    "ad",
                    "12:00",
                    0,
                    None,
                    None,
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.run_migration(
            "--dry-run",
            "--admin-username",
            "target_admin",
        )
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        self.assertIn('"existing_user_action": "reject"', result.stdout)


if __name__ == "__main__":
    unittest.main()
