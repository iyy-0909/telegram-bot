import io
import logging
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import listener_auto_catchup
from bot.bulk_replace import error_text
from bot.listener_catchup import build_listener_catchup_plan
from bot.logger import SensitiveDataFilter
from db.crud_listener import normalize_task_data
from utils.redaction import (
    is_masked_secret,
    mask_phone,
    redact_sensitive_data,
    redact_sensitive_text,
)


class RedactionTests(unittest.TestCase):
    def test_display_secret_placeholders_are_never_valid_credentials(self):
        self.assertTrue(is_masked_secret("******"))
        self.assertTrue(is_masked_secret("<hidden>"))
        self.assertTrue(is_masked_secret("<HIDDEN-BOT-TOKEN>"))
        self.assertFalse(is_masked_secret("123456:real-looking-token-value"))

    def test_sensitive_text_redacts_common_credentials_and_account_fields(self):
        secrets = {
            "bearer": "header-token-123456789",
            "password": "Sup3rPassword!",
            "api_key": "api-key-private-value",
            "access_token": "access-token-private-value",
            "session_token": "session-token-private-value",
            "password_hash": "stored-password-hash",
            "token": "generic-private-token",
            "api_secret": "api-private-secret",
            "phone": "+8613800138000",
            "session_path": "data/accounts/private-user.session",
        }
        raw = (
            f"Authorization: Bearer {secrets['bearer']} | "
            f'password="{secrets["password"]}" | '
            f"api_key={secrets['api_key']}&access_token={secrets['access_token']} | "
            f"session_token={secrets['session_token']} | "
            f"password_hash={secrets['password_hash']} | token={secrets['token']} | "
            f"api_secret={secrets['api_secret']} | phone={secrets['phone']} | "
            f"session_path={secrets['session_path']}"
        )

        safe = redact_sensitive_text(raw)

        for secret in secrets.values():
            self.assertNotIn(secret, safe)
        self.assertIn("Authorization: <hidden>", safe)
        self.assertIn("phone=<hidden-phone>", safe)
        self.assertIn("session_path=<hidden-session-path>", safe)

    def test_sensitive_text_redacts_structured_strings_and_unlabeled_tokens(self):
        jwt = "abcdefgh.ijklmnop.qrstuvwx"
        aws_key = "AKIAABCDEFGHIJKLMNOP"
        private_key = (
            "-----BEGIN PRIVATE KEY-----\nprivate-material\n"
            "-----END PRIVATE KEY-----"
        )
        raw = (
            "{'password': 'dictionary-secret'} "
            '"client_secret": "json-secret" '
            f"{jwt} {aws_key} {private_key} data/users/account.session"
        )

        safe = redact_sensitive_text(raw)

        for secret in (
            "dictionary-secret",
            "json-secret",
            jwt,
            aws_key,
            "private-material",
            "data/users/account.session",
        ):
            self.assertNotIn(secret, safe)

    def test_sensitive_data_uses_key_aware_redaction_and_phone_mask(self):
        raw = {
            "password": "password-value",
            "password_hash": "stored-password-hash",
            "token": "generic-token-value",
            "api_secret": "api-secret-value",
            "secret": "generic-secret-value",
            "nested": {
                "accessToken": "access-value",
                "phone_number": "+8613800138000",
                "session_path": "data/accounts/private.session",
            },
            "message": "proxy=http://alice:secret@example.test:8080",
        }

        safe = redact_sensitive_data(raw)

        self.assertEqual(safe["password"], "<hidden>")
        self.assertEqual(safe["password_hash"], "<hidden>")
        self.assertEqual(safe["token"], "<hidden>")
        self.assertEqual(safe["api_secret"], "<hidden>")
        self.assertEqual(safe["secret"], "<hidden>")
        self.assertEqual(safe["nested"]["accessToken"], "<hidden>")
        self.assertEqual(safe["nested"]["phone_number"], "86****00")
        self.assertEqual(
            safe["nested"]["session_path"],
            "<hidden-session-path>",
        )
        self.assertNotIn("alice", safe["message"])
        self.assertNotIn("secret", safe["message"])

    def test_mask_phone_never_returns_the_full_value(self):
        self.assertEqual(mask_phone(None), "")
        self.assertEqual(mask_phone("12345"), "****")
        self.assertEqual(mask_phone("+86 138-0013-8000"), "86****00")

    def test_logging_filter_redacts_formatted_message_and_traceback(self):
        record = logging.LogRecord(
            "clonebot",
            logging.ERROR,
            __file__,
            1,
            "phone=%s session_path=%s password=%s",
            (
                "+8613800138000",
                "data/accounts/private.session",
                "message-password",
            ),
            None,
        )
        try:
            raise RuntimeError("api_key=traceback-private-key")
        except RuntimeError:
            record.exc_info = sys.exc_info()

        SensitiveDataFilter().filter(record)

        rendered = f"{record.getMessage()}\n{record.exc_text}"
        for secret in (
            "+8613800138000",
            "data/accounts/private.session",
            "message-password",
            "traceback-private-key",
        ):
            self.assertNotIn(secret, rendered)

    def test_global_log_record_filter_protects_unrelated_loggers(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        unrelated_logger = logging.getLogger("third.party.redaction.test")
        unrelated_logger.handlers = [handler]
        unrelated_logger.propagate = False
        unrelated_logger.setLevel(logging.ERROR)

        try:
            unrelated_logger.error(
                "token=%s phone=%s session_path=%s",
                "global-private-token",
                "+8613800138000",
                "data/accounts/private.session",
            )
        finally:
            unrelated_logger.removeHandler(handler)
            handler.close()

        rendered = stream.getvalue()
        for secret in (
            "global-private-token",
            "+8613800138000",
            "data/accounts/private.session",
        ):
            self.assertNotIn(secret, rendered)

    def test_exception_helpers_and_listener_storage_are_redacted(self):
        raw_error = "password=private-value session_path=data/u/private.session"
        self.assertNotIn("private-value", error_text(RuntimeError(raw_error)))

        normalized = normalize_task_data({"last_error": raw_error})
        self.assertNotIn("private-value", normalized["last_error"])
        self.assertNotIn("data/u/private.session", normalized["last_error"])


class CatchupRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_error_response_is_redacted(self):
        secret = "plan-private-token"

        class FailingClient:
            def is_connected(self):
                return True

            def iter_messages(self, *_args, **_kwargs):
                async def iterator():
                    raise RuntimeError(f"access_token={secret}")
                    yield None

                return iterator()

        task = SimpleNamespace(
            id=91,
            account_id=7,
            source_channel="@source",
            target_channels='["@target"]',
            name="test",
        )

        with (
            patch(
                "bot.listener_catchup.account_manager.get_client",
                return_value=FailingClient(),
            ),
            patch(
                "bot.listener_catchup.get_last_success_by_target",
                return_value={"@target": None},
            ),
        ):
            result = await build_listener_catchup_plan(task)

        self.assertFalse(result["ok"])
        self.assertNotIn(secret, result["message"])

    async def test_background_error_and_queue_state_are_redacted(self):
        secret = "background-private-token"
        task = SimpleNamespace(id=92)

        with (
            patch(
                "bot.listener_auto_catchup.catchup_latest_listener_message",
                AsyncMock(side_effect=RuntimeError(f"session_token={secret}")),
            ),
            patch.object(listener_auto_catchup.runtime_queue_state, "finish") as finish,
        ):
            result = await listener_auto_catchup.run_listener_catchup_background(
                task,
                force=False,
                limit=1,
                queue_item_id="queue-92",
            )

        self.assertFalse(result["ok"])
        self.assertNotIn(secret, result["message"])
        self.assertNotIn(secret, finish.call_args.kwargs["error"])


if __name__ == "__main__":
    unittest.main()
