import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.captcha import CaptchaError, CaptchaManager
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
from db.database import Base
from db.models import UserAccount, UserSession


class AuthSecurityTests(unittest.TestCase):
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

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
