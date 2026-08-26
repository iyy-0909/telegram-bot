import hashlib
import hmac
import re
import secrets


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390_000
USERNAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{3,23}$")
RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "root",
    "system",
    "support",
}


class UsernameValidationError(ValueError):
    pass


class PasswordValidationError(ValueError):
    pass


def normalize_username(value: str) -> str:
    return (value or "").strip().lower()


def validate_username(value: str) -> str:
    username = normalize_username(value)
    if not USERNAME_PATTERN.fullmatch(username):
        raise UsernameValidationError("用户名需为 4-24 位，以字母开头，仅支持字母、数字和下划线")
    if username in RESERVED_USERNAMES:
        raise UsernameValidationError("该用户名不可注册，请更换后重试")
    return username


def validate_password(value: str) -> str:
    password = value or ""
    if len(password) < 8:
        raise PasswordValidationError("密码至少需要 8 位")
    if len(password) > 128:
        raise PasswordValidationError("密码不能超过 128 位")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise PasswordValidationError("密码必须同时包含字母和数字")
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        (
            PASSWORD_SCHEME,
            str(PASSWORD_ITERATIONS),
            salt.hex(),
            digest.hex(),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_text, salt_hex, expected_hex = (encoded or "").split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def hash_session_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()
