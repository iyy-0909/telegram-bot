import re


REDACTED_VALUE = "<hidden>"
MASKED_SECRET_VALUES = frozenset({
    REDACTED_VALUE,
    "******",
    "<hidden-bot-token>",
})

_URL_CREDENTIALS_RE = re.compile(
    r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^/\s@]+@",
    re.IGNORECASE,
)
_LABELED_BARE_CREDENTIALS_RE = re.compile(
    r"(?P<label>\b(?:proxy|proxies|http_proxy|https_proxy|all_proxy)\s*=\s*)"
    r"[^:/\s@]+:[^@\s/]+@",
    re.IGNORECASE,
)
_TELEGRAM_BOT_PATH_RE = re.compile(r"/bot[^/\s]+", re.IGNORECASE)
_TELEGRAM_BOT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])\d{5,}:[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_])"
)
_AUTHORIZATION_RE = re.compile(
    r"(?P<prefix>\bauthorization\s*[:=]\s*)(?:bearer|basic)\s+[^\s,;|]+",
    re.IGNORECASE,
)
_BEARER_TOKEN_RE = re.compile(
    r"(?P<prefix>\bbearer\s+)[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
_COOKIE_HEADER_RE = re.compile(
    r"(?P<prefix>\b(?:cookie|set-cookie)\s*[:=]\s*)[^\r\n]+",
    re.IGNORECASE,
)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)
_AWS_ACCESS_KEY_RE = re.compile(
    r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)

_SENSITIVE_KEY_PATTERN = (
    r"(?:password(?:[_-]?hash)?|passwd|passphrase|pwd|credential|"
    r"api[_-]?key|x[_-]?api[_-]?key|secret[_-]?key|private[_-]?key|"
    r"api[_-]?secret|consumer[_-]?(?:key|secret)|"
    r"access[_-]?token|refresh[_-]?token|session[_-]?token|auth[_-]?token|"
    r"id[_-]?token|csrf[_-]?token|client[_-]?secret|webhook[_-]?secret|"
    r"bot[_-]?token|telegram[_-]?token|support[_-]?bot[_-]?token|"
    r"encrypted[_-]?token|session[_-]?string|api[_-]?hash|"
    r"sessionid|session[_-]?id|token|secret)"
)
_DOUBLE_QUOTED_SECRET_RE = re.compile(
    rf'(?P<prefix>"{_SENSITIVE_KEY_PATTERN}"\s*:\s*)"(?:\\.|[^"\\])*"',
    re.IGNORECASE,
)
_SINGLE_QUOTED_SECRET_RE = re.compile(
    rf"(?P<prefix>'{_SENSITIVE_KEY_PATTERN}'\s*:\s*)'(?:\\.|[^'\\])*'",
    re.IGNORECASE,
)
_LABELED_SECRET_RE = re.compile(
    rf"(?P<prefix>\b{_SENSITIVE_KEY_PATTERN}\b\s*[:=]\s*)"
    r"(?P<quote>['\"]?)[^\s,;|&\]\}]+(?P=quote)",
    re.IGNORECASE,
)
_LABELED_PHONE_RE = re.compile(
    r"(?P<prefix>\b(?:phone|phone_number|mobile)\s*[:=]\s*)"
    r"(?P<quote>['\"]?)[^\s,;|&\]\}]+(?P=quote)",
    re.IGNORECASE,
)
_LABELED_SESSION_PATH_RE = re.compile(
    r"(?P<prefix>\b(?:session_path|session_file)\s*[:=]\s*)"
    r"(?P<quote>['\"]?)[^\r\n,;|\}\]]+(?P=quote)",
    re.IGNORECASE,
)
_SESSION_FILE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[A-Za-z]:)?[A-Za-z0-9_.\\/-]+\.session(?:-journal)?",
    re.IGNORECASE,
)

_SENSITIVE_DATA_KEYS = {
    "password",
    "passwordhash",
    "passwd",
    "passphrase",
    "pwd",
    "credential",
    "apikey",
    "xapikey",
    "secretkey",
    "privatekey",
    "apisecret",
    "consumerkey",
    "consumersecret",
    "accesstoken",
    "refreshtoken",
    "sessiontoken",
    "authtoken",
    "idtoken",
    "csrftoken",
    "clientsecret",
    "webhooksecret",
    "bottoken",
    "telegramtoken",
    "supportbottoken",
    "encryptedtoken",
    "sessionstring",
    "apihash",
    "sessionid",
    "token",
    "secret",
    "authorization",
    "cookie",
    "setcookie",
}
_PHONE_DATA_KEYS = {"phone", "phonenumber", "mobile", "mobilephone"}
_SESSION_PATH_DATA_KEYS = {"sessionpath", "sessionfile"}


def _normalized_key(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def is_masked_secret(value) -> bool:
    """Return whether a submitted value is a display-only secret placeholder."""
    return str(value or "").strip().lower() in MASKED_SECRET_VALUES


def mask_phone(value) -> str:
    """Return a stable display mask without retaining the full phone number."""
    text = str(value or "").strip()
    if not text:
        return ""

    digits = re.sub(r"\D", "", text)
    if len(digits) < 7:
        return "****"
    return f"{digits[:2]}****{digits[-2:]}"


def _replace_labeled(match, replacement=REDACTED_VALUE) -> str:
    quote = match.groupdict().get("quote") or ""
    return f"{match.group('prefix')}{quote}{replacement}{quote}"


def redact_url_credentials(value) -> str:
    text = str(value or "")
    text = _URL_CREDENTIALS_RE.sub(
        lambda match: f"{match.group('scheme')}<hidden>@",
        text,
    )
    return _LABELED_BARE_CREDENTIALS_RE.sub(
        lambda match: f"{match.group('label')}<hidden>@",
        text,
    )


def redact_telegram_bot_tokens(value) -> str:
    text = str(value or "")
    text = _TELEGRAM_BOT_PATH_RE.sub("/bot<hidden>", text)
    return _TELEGRAM_BOT_TOKEN_RE.sub("<hidden-bot-token>", text)


def redact_sensitive_text(value) -> str:
    text = str(value or "")
    text = _PRIVATE_KEY_RE.sub("<hidden-private-key>", text)
    text = _AUTHORIZATION_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED_VALUE}",
        text,
    )
    text = _COOKIE_HEADER_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED_VALUE}",
        text,
    )
    text = _DOUBLE_QUOTED_SECRET_RE.sub(
        lambda match: f'{match.group("prefix")}"{REDACTED_VALUE}"',
        text,
    )
    text = _SINGLE_QUOTED_SECRET_RE.sub(
        lambda match: f"{match.group('prefix')}'{REDACTED_VALUE}'",
        text,
    )
    text = _LABELED_SECRET_RE.sub(_replace_labeled, text)
    text = _LABELED_PHONE_RE.sub(
        lambda match: _replace_labeled(match, "<hidden-phone>"),
        text,
    )
    text = _LABELED_SESSION_PATH_RE.sub(
        lambda match: _replace_labeled(match, "<hidden-session-path>"),
        text,
    )
    text = _SESSION_FILE_PATH_RE.sub("<hidden-session-path>", text)
    text = _BEARER_TOKEN_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED_VALUE}",
        text,
    )
    text = _JWT_RE.sub("<hidden-jwt>", text)
    text = _AWS_ACCESS_KEY_RE.sub("<hidden-access-key>", text)
    return redact_url_credentials(redact_telegram_bot_tokens(text))


def redact_sensitive_data(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized_key = _normalized_key(key)
            if normalized_key in _SENSITIVE_DATA_KEYS:
                result[key] = REDACTED_VALUE if item not in (None, "") else item
            elif normalized_key in _PHONE_DATA_KEYS:
                result[key] = mask_phone(item)
            elif normalized_key in _SESSION_PATH_DATA_KEYS:
                result[key] = "<hidden-session-path>" if item else item
            else:
                result[key] = redact_sensitive_data(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    if isinstance(value, set):
        return {redact_sensitive_data(item) for item in value}
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value
