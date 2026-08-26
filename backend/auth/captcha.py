import base64
import hashlib
import hmac
import os
import random
import secrets
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np


CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class CaptchaError(ValueError):
    pass


@dataclass
class CaptchaChallenge:
    answer_hash: str
    expires_at: float
    attempts_left: int


class CaptchaManager:
    def __init__(self, ttl_seconds=None, max_attempts=3):
        self.ttl_seconds = int(
            ttl_seconds or os.getenv("CAPTCHA_EXPIRE_SECONDS", "300")
        )
        self.max_attempts = max_attempts
        self._secret = secrets.token_bytes(32)
        self._items = {}
        self._lock = threading.Lock()

    def _answer_hash(self, challenge_id, answer):
        payload = f"{challenge_id}:{(answer or '').strip().upper()}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def create(self):
        challenge_id = secrets.token_urlsafe(24)
        answer = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(5))
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            self._items[challenge_id] = CaptchaChallenge(
                answer_hash=self._answer_hash(challenge_id, answer),
                expires_at=now + self.ttl_seconds,
                attempts_left=self.max_attempts,
            )
        return {
            "captcha_id": challenge_id,
            "image": self._render_data_url(answer),
            "expires_in": self.ttl_seconds,
        }

    def verify(self, challenge_id, answer):
        challenge_key = (challenge_id or "").strip()
        user_answer = (answer or "").strip().upper()
        if not challenge_key or not user_answer:
            raise CaptchaError("请输入图形验证码")

        now = time.time()
        with self._lock:
            self._purge_expired(now)
            challenge = self._items.get(challenge_key)
            if not challenge:
                raise CaptchaError("验证码已失效，请刷新后重试")

            actual_hash = self._answer_hash(challenge_key, user_answer)
            if hmac.compare_digest(actual_hash, challenge.answer_hash):
                self._items.pop(challenge_key, None)
                return True

            challenge.attempts_left -= 1
            if challenge.attempts_left <= 0:
                self._items.pop(challenge_key, None)
                raise CaptchaError("验证码错误次数过多，请刷新后重试")
            raise CaptchaError("图形验证码错误")

    def _purge_expired(self, now):
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    @staticmethod
    def _render_data_url(answer):
        rng = random.SystemRandom()
        image = np.full((52, 160, 3), (248, 246, 242), dtype=np.uint8)

        for _ in range(9):
            start = (rng.randint(0, 159), rng.randint(0, 51))
            end = (rng.randint(0, 159), rng.randint(0, 51))
            color = rng.choice(((208, 197, 181), (220, 207, 194), (198, 186, 171)))
            cv2.line(image, start, end, color, 1, cv2.LINE_AA)

        for _ in range(24):
            center = (rng.randint(0, 159), rng.randint(0, 51))
            color = rng.choice(((206, 194, 180), (218, 204, 190), (194, 183, 169)))
            cv2.circle(image, center, 1, color, -1, cv2.LINE_AA)

        for index, character in enumerate(answer):
            x = 12 + index * 29 + rng.randint(-1, 2)
            y = 38 + rng.randint(-3, 3)
            color = rng.choice(((77, 53, 35), (91, 62, 39), (67, 48, 34)))
            cv2.putText(
                image,
                character,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.85,
                color,
                2,
                cv2.LINE_AA,
            )

        ok, encoded_image = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("captcha image generation failed")
        encoded = base64.b64encode(encoded_image.tobytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"


captcha_manager = CaptchaManager()
