import asyncio
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

import init_db as init_db_module
from auth.captcha import CaptchaError, CaptchaManager
from auth.access import (
    effective_feature_keys,
    expand_feature_dependencies,
)
from auth.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from auth.security import (
    PasswordValidationError,
    UsernameValidationError,
    hash_password,
    validate_password,
    validate_username,
    verify_password,
)
from api import server
from db import crud_users
from db.crud_support import message_to_dict as support_message_to_dict
from db.database import Base
from db.models import UserAccount, UserSession


class AuthSecurityTests(unittest.TestCase):
    def test_feature_dependencies_expand_to_a_usable_permission_set(self):
        self.assertEqual(
            expand_feature_dependencies(["listener_tasks"]),
            ["listener_tasks", "bots", "accounts"],
        )
        self.assertEqual(
            expand_feature_dependencies(["clone_tasks", "notifications"]),
            ["clone_tasks", "bots", "accounts", "notifications"],
        )

    def test_incomplete_legacy_feature_grants_fail_closed(self):
        self.assertEqual(
            effective_feature_keys("user", '["dashboard","listener_tasks"]'),
            ["dashboard"],
        )
        self.assertEqual(
            effective_feature_keys(
                "user",
                '["listener_tasks","accounts","bots"]',
            ),
            ["listener_tasks", "bots", "accounts"],
        )

    def test_username_is_normalized_and_validated(self):
        self.assertEqual(validate_username("  Demo_User1 "), "demo_user1")
        with self.assertRaises(UsernameValidationError):
            validate_username("1234")
        with self.assertRaises(UsernameValidationError):
            validate_username("admin")

    def test_password_requires_letters_and_numbers(self):
        self.assertEqual(validate_password("secure123"), "secure123")
        with self.assertRaises(PasswordValidationError):
            validate_password("onlyletters")
        with self.assertRaises(PasswordValidationError):
            validate_password("12345678")

    def test_password_hash_is_salted_and_verifiable(self):
        first = hash_password("secure123")
        second = hash_password("secure123")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("secure123", first))
        self.assertFalse(verify_password("wrong123", first))

    def test_legacy_support_settings_never_return_plaintext_bot_token(self):
        secret = "123456789:AAExampleSecretToken"
        raw_settings = {
            "support_bot_token": secret,
            "welcome_message": "hello",
        }

        with (
            patch.object(server, "ensure_support_defaults"),
            patch.object(server, "get_support_settings", return_value=raw_settings),
        ):
            response = server.api_support_settings()

        settings = response["settings"]
        self.assertEqual(settings["support_bot_token"], "")
        self.assertEqual(settings["support_bot_token_masked"], "******")
        self.assertTrue(settings["has_support_bot_token"])
        self.assertNotIn(secret, json.dumps(response))

    def test_empty_legacy_support_token_does_not_clear_stored_secret(self):
        secret = "123456789:AAExampleSecretToken"
        updated_settings = {
            "support_bot_token": secret,
            "welcome_message": "updated",
        }

        with patch.object(
            server,
            "update_support_settings",
            return_value=updated_settings,
        ) as update_settings:
            response = server.api_support_update_settings(
                server.SupportSettingsUpdate(
                    support_bot_token="   ",
                    welcome_message="updated",
                )
            )

        update_settings.assert_called_once_with({"welcome_message": "updated"})
        self.assertFalse(response["settings"]["support_bot_token"])
        self.assertTrue(response["settings"]["has_support_bot_token"])
        self.assertNotIn(secret, json.dumps(response))

    def test_bot_options_exclude_secrets_and_diagnostics(self):
        bot = SimpleNamespace(
            id=7,
            name="Delivery Bot",
            username="delivery_bot",
            bot_link="https://t.me/delivery_bot",
            enabled=True,
            token="123456789:AAExampleSecretToken",
            remark="private note",
            last_error="proxy=http://user:password@example.test:8080",
        )

        with patch.object(server, "get_all_bots", return_value=[bot]):
            response = server.bot_options()

        self.assertEqual(
            response,
            [{
                "id": 7,
                "name": "Delivery Bot",
                "username": "delivery_bot",
                "bot_link": "https://t.me/delivery_bot",
                "enabled": True,
            }],
        )

    def test_sensitive_error_text_redacts_proxy_credentials_and_bot_tokens(self):
        bot_token = "123456789:AAExampleSecretTokenValue"
        raw = (
            "proxy=socks5://alice:secret@example.test:1080 "
            f"url=https://api.telegram.org/bot{bot_token}/getMe "
            f"token={bot_token}"
        )

        safe = server.redact_sensitive_text(raw)

        self.assertNotIn("alice", safe)
        self.assertNotIn("secret", safe)
        self.assertNotIn(bot_token, safe)
        self.assertIn("socks5://<hidden>@example.test:1080", safe)
        self.assertIn("/bot<hidden>/getMe", safe)

    def test_historical_bot_error_is_redacted_in_management_response(self):
        bot_token = "123456789:AAExampleSecretTokenValue"
        bot = SimpleNamespace(
            id=9,
            name="Delivery Bot",
            token=bot_token,
            username="delivery_bot",
            bot_link="https://t.me/delivery_bot",
            enabled=True,
            remark="",
            last_error=(
                "proxy=http://alice:secret@example.test:8080 "
                f"https://api.telegram.org/bot{bot_token}/getMe"
            ),
            created_at=None,
            updated_at=None,
        )

        response = server.bot_to_dict(bot)

        self.assertNotIn("alice", response["last_error"])
        self.assertNotIn("secret", response["last_error"])
        self.assertNotIn(bot_token, response["last_error"])
        self.assertEqual(response["token"], "******")

    def test_historical_support_message_error_is_redacted(self):
        bot_token = "123456789:AAExampleSecretTokenValue"
        raw_error = (
            "proxy=http://alice:secret@example.test:8080 "
            f"https://api.telegram.org/bot{bot_token}/sendMessage"
        )
        message = SimpleNamespace(
            id=1,
            support_bot_id=2,
            conversation_id=3,
            customer_id=4,
            sender_type="bot",
            sender_id="",
            message_type="text",
            text="",
            caption="",
            file_id="",
            file_unique_id="",
            file_name="",
            mime_type="",
            file_size=None,
            width=None,
            height=None,
            duration=None,
            telegram_message_id=None,
            support_group_message_id=None,
            reply_to_support_group_message_id=None,
            send_status="failed",
            error_message=raw_error,
            status="failed",
            error=raw_error,
            created_at=None,
        )

        response = support_message_to_dict(message)

        self.assertNotIn("alice", response["error_message"])
        self.assertNotIn("secret", response["error"])
        self.assertNotIn(bot_token, json.dumps(response))

    def test_regular_dashboard_returns_counts_without_business_details(self):
        queue_snapshot = {
            "current": {"task_name": "private task", "source_channel": "@secret"},
            "waiting": [{"task_id": 7, "target_channel": "@private"}],
            "recent": [{"error": "private error"}],
            "stats": {
                "waiting_count": 1,
                "sending_count": 1,
                "recent_count": 1,
                "failed_count": 1,
            },
        }
        clone_snapshot = {"running_task_ids": [99], "total_running": 1}
        request = SimpleNamespace(
            state=SimpleNamespace(
                current_user={"role": "user", "feature_keys": ["dashboard"]},
            ),
        )

        with (
            patch.object(server.runtime_queue_state, "snapshot", return_value=queue_snapshot),
            patch.object(server, "get_all_listener_tasks", return_value=[SimpleNamespace(enabled=True)]),
            patch.object(server, "get_all_clone_tasks", return_value=[]),
            patch.object(server, "get_all_accounts", return_value=[SimpleNamespace(id=13)]),
            patch.object(server.clone_manager, "snapshot", return_value=clone_snapshot),
            patch.object(server.account_manager, "clients", {13: object()}),
        ):
            response = server.api_runtime_dashboard(request)

        self.assertIsNone(response["queue"]["current"])
        self.assertEqual(response["queue"]["waiting"], [])
        self.assertEqual(response["queue"]["recent"], [])
        self.assertEqual(response["queue"]["stats"], {
            "waiting_count": 0,
            "sending_count": 0,
            "recent_count": 0,
            "failed_count": 0,
        })
        self.assertEqual(response["clone_workers"]["running_task_ids"], [])
        self.assertEqual(response["clone_workers"]["total_running"], 0)
        self.assertEqual(response["accounts"]["loaded_ids"], [])
        self.assertEqual(response["accounts"]["loaded_count"], 1)


class CaptchaTests(unittest.TestCase):
    def test_captcha_is_png_and_can_only_be_used_once(self):
        manager = CaptchaManager(ttl_seconds=60)
        with patch("auth.captcha.secrets.choice", side_effect=list("ABCDE")):
            challenge = manager.create()

        self.assertTrue(challenge["image"].startswith("data:image/png;base64,"))
        self.assertTrue(manager.verify(challenge["captcha_id"], "abcde"))
        with self.assertRaises(CaptchaError):
            manager.verify(challenge["captcha_id"], "ABCDE")

    def test_captcha_expires_after_repeated_failures(self):
        manager = CaptchaManager(ttl_seconds=60, max_attempts=2)
        with patch("auth.captcha.secrets.choice", side_effect=list("ABCDE")):
            challenge = manager.create()

        with self.assertRaisesRegex(CaptchaError, "图形验证码错误"):
            manager.verify(challenge["captcha_id"], "ZZZZZ")
        with self.assertRaisesRegex(CaptchaError, "错误次数过多"):
            manager.verify(challenge["captcha_id"], "YYYYY")


class RateLimitTests(unittest.TestCase):
    def test_rate_limit_blocks_after_limit(self):
        limiter = SlidingWindowRateLimiter()
        limiter.hit("register:test", 2, 60)
        limiter.hit("register:test", 2, 60)
        with self.assertRaises(RateLimitExceeded):
            limiter.hit("register:test", 2, 60)


class UserSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "auth.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(
            self.engine,
            tables=[UserAccount.__table__, UserSession.__table__],
        )
        self.session_local = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        self.session_patch = patch.object(
            crud_users,
            "SessionLocal",
            self.session_local,
        )
        self.session_patch.start()
        self.defaults_patch = patch.object(server, "ensure_defaults_for_owner")
        self.defaults_patch.start()

    def tearDown(self):
        self.defaults_patch.stop()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_user_can_create_login_session_and_revoke_it(self):
        user = crud_users.create_user("demo_user", hash_password("secure123"))
        token, expires_at = crud_users.create_user_session(user.id, session_days=7)

        resolved = crud_users.get_user_by_session_token(token)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved[0]["username"], "demo_user")
        self.assertGreater(expires_at, user.created_at)

        self.assertTrue(crud_users.revoke_user_session(token))
        self.assertIsNone(crud_users.get_user_by_session_token(token))

    def test_register_then_login_api_flow(self):
        manager = CaptchaManager(ttl_seconds=60)
        with patch("auth.captcha.secrets.choice", side_effect=list("ABCDE")):
            challenge = manager.create()
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1")
        )

        with (
            patch.object(server, "captcha_manager", manager),
            patch.object(server, "USER_REGISTRATION_ENABLED", False),
        ):
            registered = asyncio.run(
                server.api_auth_register(
                    server.RegisterRequest(
                        username="new_user",
                        password="secure123",
                        captcha_id=challenge["captcha_id"],
                        captcha_code="ABCDE",
                    ),
                    request,
                )
            )

        self.assertEqual(registered["user"]["username"], "new_user")
        self.assertEqual(registered["user"]["role"], "admin")
        self.assertNotIn("password_hash", registered["user"])
        self.assertTrue(registered["token"])

        logged_in = asyncio.run(
            server.api_auth_login(
                server.LoginRequest(username="new_user", password="secure123"),
                request,
            )
        )
        self.assertEqual(logged_in["user"]["username"], "new_user")
        self.assertTrue(logged_in["token"])

    def test_remote_request_cannot_create_first_admin(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.10"),
            headers={},
        )
        with (
            patch.object(server, "USER_REGISTRATION_ENABLED", False),
            patch.object(server.captcha_manager, "verify", return_value=True),
            patch("api.server._apply_auth_rate_limit"),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(
                    server.api_auth_register(
                        server.RegisterRequest(
                            username="remote_user",
                            password="secure123",
                            captcha_id="remote-captcha",
                            captcha_code="ABCDE",
                        ),
                        request,
                    )
                )

        self.assertEqual(caught.exception.status_code, 403)
        db = self.session_local()
        try:
            self.assertEqual(db.query(UserAccount).count(), 0)
        finally:
            db.close()

    def test_registration_stays_closed_after_bootstrap_by_default(self):
        crud_users.create_user("existing_user", hash_password("secure123"))
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )
        with (
            patch.object(server, "USER_REGISTRATION_ENABLED", False),
            patch.object(server.captcha_manager, "verify", return_value=True),
            patch("api.server._apply_auth_rate_limit"),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(
                    server.api_auth_register(
                        server.RegisterRequest(
                            username="second_user",
                            password="secure123",
                            captcha_id="second-captcha",
                            captcha_code="ABCDE",
                        ),
                        request,
                    )
                )

        self.assertEqual(caught.exception.status_code, 403)

    def test_explicit_registration_creates_read_only_user(self):
        crud_users.create_user("existing_user", hash_password("secure123"))
        request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.10"),
            headers={},
        )
        with (
            patch.object(server, "USER_REGISTRATION_ENABLED", True),
            patch.object(server.captcha_manager, "verify", return_value=True),
            patch("api.server._apply_auth_rate_limit"),
        ):
            registered = asyncio.run(
                server.api_auth_register(
                    server.RegisterRequest(
                        username="readonly_user",
                        password="secure123",
                        captcha_id="enabled-captcha",
                        captcha_code="ABCDE",
                    ),
                    request,
                )
            )

        self.assertEqual(registered["user"]["role"], "user")
        self.assertEqual(registered["user"]["plan_tier"], "free")
        self.assertEqual(
            registered["user"]["feature_keys"],
            ["dashboard", "listener_tasks", "clone_tasks", "bots", "accounts"],
        )
        self.assertEqual(registered["user"]["access_state"], "active")
        self.assertIsNone(registered["user"]["access_expires_at"])
        self.assertTrue(registered["user"]["available"])

        with patch("api.server._apply_auth_rate_limit"):
            logged_in = asyncio.run(
                server.api_auth_login(
                    server.LoginRequest(
                        username="readonly_user",
                        password="secure123",
                    ),
                    request,
                )
            )
        self.assertEqual(logged_in["user"]["access_state"], "active")
        self.assertTrue(logged_in["token"])

    def test_concurrent_bootstrap_creates_only_one_admin(self):
        start = threading.Barrier(2)

        def register(username):
            start.wait(timeout=5)
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                headers={},
            )
            try:
                return asyncio.run(
                    server.api_auth_register(
                        server.RegisterRequest(
                            username=username,
                            password="secure123",
                            captcha_id=f"captcha-{username}",
                            captcha_code="ABCDE",
                        ),
                        request,
                    )
                )
            except HTTPException as exc:
                return exc

        with (
            patch.object(server, "USER_REGISTRATION_ENABLED", False),
            patch.object(server.captcha_manager, "verify", return_value=True),
            patch("api.server._apply_auth_rate_limit"),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(
                executor.map(register, ("first_admin", "second_admin"))
            )

        successes = [item for item in results if isinstance(item, dict)]
        failures = [item for item in results if isinstance(item, HTTPException)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(successes[0]["user"]["role"], "admin")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].status_code, 403)

        db = self.session_local()
        try:
            self.assertEqual(db.query(UserAccount).count(), 1)
            self.assertEqual(
                db.query(UserAccount).filter(UserAccount.role == "admin").count(),
                1,
            )
        finally:
            db.close()

    def test_regular_user_can_only_access_own_auth_endpoints(self):
        def build_request(method, path, token="member-session"):
            return Request({
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            })

        session = (
            {"id": 2, "username": "member", "role": "user"},
            12,
        )
        with (
            patch.object(server, "ADMIN_TOKEN", ""),
            patch("api.server.get_user_by_session_token", return_value=session),
        ):
            for method, path in (
                ("GET", "/api/accounts"),
                ("GET", "/api/bots/9/test"),
                ("POST", "/api/bots"),
                ("PUT", "/api/accounts/7"),
                ("PATCH", "/api/tasks/7"),
                ("DELETE", "/api/rules/7"),
            ):
                call_next = AsyncMock(
                    return_value=server.Response(status_code=204)
                )
                response = asyncio.run(
                    server.require_admin_auth(
                        build_request(method, path),
                        call_next,
                    )
                )
                self.assertEqual(response.status_code, 403)
                call_next.assert_not_awaited()

            for method, path in (
                ("GET", "/api/auth/me"),
                ("POST", "/api/auth/logout"),
            ):
                call_next = AsyncMock(
                    return_value=server.Response(status_code=204)
                )
                response = asyncio.run(
                    server.require_admin_auth(
                        build_request(method, path),
                        call_next,
                    )
                )
                self.assertEqual(response.status_code, 204)
                call_next.assert_awaited_once()

        admin_session = (
            {"id": 1, "username": "admin-user", "role": "admin"},
            13,
        )
        with (
            patch.object(server, "ADMIN_TOKEN", ""),
            patch(
                "api.server.get_user_by_session_token",
                return_value=admin_session,
            ),
        ):
            for method, path in (
                ("GET", "/api/accounts"),
                ("GET", "/api/bots/9/test"),
                ("POST", "/api/bots"),
            ):
                call_next = AsyncMock(
                    return_value=server.Response(status_code=204)
                )
                response = asyncio.run(
                    server.require_admin_auth(
                        build_request(method, path, "admin-session"),
                        call_next,
                    )
                )
                self.assertEqual(response.status_code, 204)
                call_next.assert_awaited_once()

    def test_feature_grant_is_visible_to_existing_session_immediately(self):
        user = crud_users.create_user("feature_user", hash_password("secure123"))
        token, _ = crud_users.create_user_session(user.id, session_days=7)

        def build_request(path, method="GET"):
            return Request({
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            })

        restricted_next = AsyncMock(return_value=server.Response(status_code=204))
        restricted = asyncio.run(
            server.require_admin_auth(
                build_request("/api/settings/ai"),
                restricted_next,
            )
        )
        self.assertEqual(restricted.status_code, 403)
        self.assertEqual(json.loads(restricted.body)["code"], "PLAN_RESTRICTED")
        restricted_next.assert_not_awaited()

        updated = crud_users.update_user_access(
            user.id,
            plan_tier="paid",
        )
        self.assertEqual(
            updated["feature_keys"],
            [
                "dashboard",
                "listener_tasks",
                "clone_tasks",
                "bots",
                "channels",
                "accounts",
                "ai_settings",
                "system_settings",
            ],
        )
        self.assertTrue(updated["available"])

        allowed_next = AsyncMock(return_value=server.Response(status_code=204))
        allowed = asyncio.run(
            server.require_admin_auth(
                build_request("/api/listener-tasks"),
                allowed_next,
            )
        )
        self.assertEqual(allowed.status_code, 204)
        allowed_next.assert_awaited_once()

        options_next = AsyncMock(return_value=server.Response(status_code=204))
        options = asyncio.run(
            server.require_admin_auth(
                build_request("/api/options/accounts"),
                options_next,
            )
        )
        self.assertEqual(options.status_code, 204)
        options_next.assert_awaited_once()

        for path in ("/api/options/bots", "/api/settings/ai", "/api/ai/prompts"):
            dependency_next = AsyncMock(
                return_value=server.Response(status_code=204)
            )
            dependency = asyncio.run(
                server.require_admin_auth(
                    build_request(path),
                    dependency_next,
                )
            )
            self.assertEqual(dependency.status_code, 204, path)
            dependency_next.assert_awaited_once()

        for method, path in (
            ("GET", "/api/accounts"),
            ("GET", "/api/bots"),
            ("POST", "/api/bots"),
        ):
            dependency_next = AsyncMock(
                return_value=server.Response(status_code=204)
            )
            dependency = asyncio.run(
                server.require_admin_auth(
                    build_request(path, method),
                    dependency_next,
                )
            )
            self.assertEqual(dependency.status_code, 204, (method, path))
            dependency_next.assert_awaited_once()

        for method, path in (
            ("PUT", "/api/settings/ai"),
            ("POST", "/api/ai/prompts"),
        ):
            mutation_next = AsyncMock(
                return_value=server.Response(status_code=204)
            )
            mutation = asyncio.run(
                server.require_admin_auth(
                    build_request(path, method),
                    mutation_next,
                )
            )
            self.assertEqual(mutation.status_code, 204, (method, path))
            mutation_next.assert_awaited_once()

    def test_expired_user_is_denied_but_can_read_own_auth_state(self):
        user = crud_users.create_user("expired_user", hash_password("secure123"))
        token, _ = crud_users.create_user_session(user.id, session_days=7)
        crud_users.update_user_access(
            user.id,
            plan_tier="free",
            access_expires_at=datetime.utcnow() - timedelta(minutes=1),
            access_expires_at_provided=True,
        )

        def build_request(path):
            return Request({
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            })

        denied_next = AsyncMock(return_value=server.Response(status_code=204))
        denied = asyncio.run(
            server.require_admin_auth(build_request("/api/status"), denied_next)
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(json.loads(denied.body)["code"], "ACCESS_EXPIRED")
        denied_next.assert_not_awaited()

        self_next = AsyncMock(return_value=server.Response(status_code=204))
        self_response = asyncio.run(
            server.require_admin_auth(build_request("/api/auth/me"), self_next)
        )
        self.assertEqual(self_response.status_code, 204)
        self_next.assert_awaited_once()

    def test_unknown_api_path_fails_closed(self):
        user = crud_users.create_user("unknown_user", hash_password("secure123"))
        crud_users.update_user_access(user.id, plan_tier="free")
        token, _ = crud_users.create_user_session(user.id, session_days=7)
        path = "/api/new-unclassified-endpoint"
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        call_next = AsyncMock(return_value=server.Response(status_code=204))
        response = asyncio.run(server.require_admin_auth(request, call_next))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.body)["code"], "API_FORBIDDEN")
        call_next.assert_not_awaited()

    def test_raw_logs_are_admin_only_even_with_dashboard_and_alerts(self):
        user = crud_users.create_user("logs_user", hash_password("secure123"))
        crud_users.update_user_access(user.id, plan_tier="paid")
        token, _ = crud_users.create_user_session(user.id, session_days=7)
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/logs",
            "raw_path": b"/api/logs",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        call_next = AsyncMock(return_value=server.Response(status_code=204))

        response = asyncio.run(server.require_admin_auth(request, call_next))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.body)["code"], "ADMIN_REQUIRED")
        call_next.assert_not_awaited()

    def test_paid_plan_does_not_grant_excluded_operations(self):
        user = crud_users.create_user("paid_user", hash_password("secure123"))
        crud_users.update_user_access(user.id, plan_tier="paid")
        token, _ = crud_users.create_user_session(user.id, session_days=7)

        for path in (
            "/api/bulk-replace/preview",
            "/api/support/bots",
            "/api/notification-settings",
            "/api/control-alerts",
        ):
            request = Request({
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            })
            call_next = AsyncMock(return_value=server.Response(status_code=204))
            response = asyncio.run(server.require_admin_auth(request, call_next))
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(
                json.loads(response.body)["code"],
                "FEATURE_FORBIDDEN",
            )
            call_next.assert_not_awaited()

    def test_admin_can_manage_user_access_but_not_an_admin(self):
        member = crud_users.create_user("managed_user", hash_password("secure123"))
        db = self.session_local()
        try:
            admin = UserAccount(
                username="owner_user",
                password_hash=hash_password("secure123"),
                role="admin",
                status="active",
                feature_keys_json="[]",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            admin_id = admin.id
        finally:
            db.close()

        request = SimpleNamespace(
            state=SimpleNamespace(
                current_user={"id": admin_id, "role": "admin"},
            )
        )
        regular_request = SimpleNamespace(
            state=SimpleNamespace(
                current_user={"id": member.id, "role": "user"},
            )
        )
        with self.assertRaises(HTTPException) as admin_only:
            server.api_admin_features(regular_request)
        self.assertEqual(admin_only.exception.status_code, 403)

        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        result = server.api_admin_update_user_access(
            member.id,
            server.UserAccessUpdate(
                plan_tier="paid",
                access_expires_at=expires_at,
                status="active",
            ),
            request,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["user"]["feature_keys"],
            [
                "dashboard",
                "listener_tasks",
                "clone_tasks",
                "bots",
                "channels",
                "accounts",
                "ai_settings",
                "system_settings",
            ],
        )
        self.assertTrue(result["user"]["access_expires_at"].endswith("Z"))
        self.assertNotIn("password_hash", result["user"])

        users = server.api_admin_users(request)["items"]
        self.assertTrue(any(item["id"] == member.id for item in users))
        self.assertTrue(all("password_hash" not in item for item in users))
        self.assertEqual(
            len(server.api_admin_features(request)["items"]),
            len(server.FEATURE_ORDER),
        )
        feature_catalog = {
            item["key"]: item
            for item in server.api_admin_features(request)["items"]
        }
        self.assertEqual(
            feature_catalog["listener_tasks"]["requires"],
            ("accounts", "bots"),
        )

        with self.assertRaises(HTTPException) as immutable:
            server.api_admin_update_user_access(
                admin_id,
                server.UserAccessUpdate(plan_tier="free"),
                request,
            )
        self.assertEqual(immutable.exception.status_code, 403)

        with self.assertRaises(HTTPException) as invalid:
            server.api_admin_update_user_access(
                member.id,
                server.UserAccessUpdate(plan_tier="not-a-plan"),
                request,
            )
        self.assertEqual(invalid.exception.status_code, 422)

    def test_account_options_do_not_expose_session_or_proxy(self):
        account = SimpleNamespace(
            id=7,
            name="Collector",
            username="collector_user",
            enabled=True,
            is_default=True,
            session_path="data/accounts/private.session",
            proxy="socks5://secret",
        )
        with patch.object(server, "get_all_accounts", return_value=[account]):
            result = server.account_options()
        self.assertEqual(
            result,
            [{
                "id": 7,
                "name": "Collector",
                "username": "collector_user",
                "enabled": True,
                "is_default": True,
            }],
        )

    def test_account_payload_masks_write_only_credentials(self):
        account = SimpleNamespace(
            id=7,
            name="Collector",
            username="collector_user",
            phone="+8613800001234",
            session_path="data/sessions/private.session",
            proxy="socks5://user:password@127.0.0.1:1080",
            enabled=True,
            is_default=False,
            remark="",
            updated_at=None,
        )

        result = server.account_to_dict(account)

        self.assertEqual(result["phone"], "")
        self.assertNotIn("13800001234", result["phone_masked"])
        self.assertTrue(result["has_phone"])
        self.assertEqual(result["session_path"], "")
        self.assertTrue(result["has_session_path"])
        self.assertEqual(result["proxy"], "")
        self.assertTrue(result["has_proxy"])
        self.assertNotIn("password", json.dumps(result))

    def test_account_request_models_ignore_client_supplied_session_path(self):
        create_payload = server.AccountCreate(
            name="Collector",
            session_path="../../other-user/session",
        ).model_dump()
        update_payload = server.AccountUpdate(
            name="Collector",
            session_path="../../other-user/session",
        ).model_dump(exclude_unset=True)
        login_payload = server.AccountLoginStart(
            phone="+8613800001234",
            session_path="../../other-user/session",
            update_existing=True,
        ).model_dump()

        self.assertNotIn("session_path", create_payload)
        self.assertNotIn("session_path", update_payload)
        self.assertNotIn("session_path", login_payload)
        self.assertNotIn("update_existing", login_payload)

    def test_bot_feature_allows_bot_profile_mutations(self):
        request = SimpleNamespace(
            state=SimpleNamespace(
                current_user={
                    "id": 9,
                    "role": "user",
                    "feature_keys": ["bots"],
                }
            )
        )
        server.require_bot_profile_admin(request)
        profile = {
            "capabilities": server.bot_profile_capabilities(True, True),
        }
        result = server.apply_profile_role_capabilities(profile, request)
        self.assertTrue(result["capabilities"]["profile"]["write"])
        self.assertTrue(result["capabilities"]["commands"]["write"])

    def test_all_business_routes_have_an_explicit_authorization_class(self):
        self_service = {
            ("GET", "/api/auth/me"),
            ("POST", "/api/auth/logout"),
        }
        unclassified = []
        for route in server.app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/"):
                continue
            for method in getattr(route, "methods", set()):
                if method == "OPTIONS":
                    continue
                if path in server.AUTH_EXEMPT_PATHS:
                    continue
                if (method, path) in self_service:
                    continue
                if path.startswith("/api/admin/"):
                    continue
                if server.is_admin_only_api(method, path):
                    continue
                if server.request_required_features(method, path) is None:
                    unclassified.append((method, path))
        self.assertEqual(unclassified, [])


class AuthClientKeyTests(unittest.TestCase):
    def test_private_proxy_uses_nearest_public_forwarded_ip(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="172.18.0.4"),
            headers={
                "x-forwarded-for": "invalid, 10.0.0.8, 8.8.8.8, 9.9.9.9",
                "x-real-ip": "1.1.1.1",
            },
        )
        self.assertEqual(server._auth_client_key(request), "9.9.9.9")

    def test_spoofed_leftmost_forwarded_ip_cannot_rotate_rate_limit_key(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="172.18.0.4"),
            headers={
                "x-forwarded-for": "8.8.8.8, 9.9.9.9",
            },
        )
        self.assertEqual(server._auth_client_key(request), "9.9.9.9")

    def test_public_direct_client_cannot_spoof_forwarded_ip(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="45.76.176.48"),
            headers={"x-forwarded-for": "8.8.8.8"},
        )
        self.assertEqual(server._auth_client_key(request), "45.76.176.48")


class AuthMigrationTests(unittest.TestCase):
    def test_init_db_refuses_to_start_with_unowned_legacy_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy-unowned.db"
            engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
            )
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE accounts (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        session_path VARCHAR NOT NULL
                    )
                """))
                connection.execute(text("""
                    INSERT INTO accounts (id, name, session_path)
                    VALUES (1, 'legacy', 'data/sessions/legacy')
                """))

            with patch.object(init_db_module, "engine", engine):
                with self.assertRaisesRegex(RuntimeError, "单一管理员归属迁移"):
                    init_db_module.init_db()

            engine.dispose()

    def test_init_db_adds_access_columns_and_preserves_existing_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy-auth.db"
            engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
            )
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE user_accounts (
                        id INTEGER PRIMARY KEY,
                        username VARCHAR(32) NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'user',
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        failed_login_count INTEGER NOT NULL DEFAULT 0,
                        locked_until DATETIME,
                        last_login_at DATETIME,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """))
                connection.execute(text("""
                    INSERT INTO user_accounts (
                        id, username, password_hash, role, status,
                        failed_login_count, created_at, updated_at
                    ) VALUES (
                        1, 'legacy_user', 'hash', 'user', 'active',
                        0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """))

            with (
                patch.object(init_db_module, "engine", engine),
                patch.object(init_db_module, "ensure_defaults"),
            ):
                init_db_module.init_db()

            columns = {
                item["name"]
                for item in inspect(engine).get_columns("user_accounts")
            }
            self.assertIn("feature_keys_json", columns)
            self.assertIn("access_expires_at", columns)
            self.assertIn("plan_tier", columns)
            self.assertIn("advertisement_text", columns)
            self.assertIn("advertisement_send_time", columns)
            with engine.connect() as connection:
                row = connection.execute(text("""
                    SELECT username, plan_tier, feature_keys_json, access_expires_at
                    FROM user_accounts WHERE id = 1
                """)).one()
            self.assertEqual(row.username, "legacy_user")
            self.assertEqual(row.plan_tier, "free")
            self.assertEqual(
                row.feature_keys_json,
                '["dashboard","listener_tasks","clone_tasks","bots","accounts"]',
            )
            self.assertIsNone(row.access_expires_at)
            self.assertEqual(
                len(list(Path(temp_dir).glob("legacy-auth.db.bak_init_db_*"))),
                1,
            )
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
