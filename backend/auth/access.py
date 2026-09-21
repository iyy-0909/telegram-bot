import json
from datetime import datetime, timezone


FEATURE_DEFINITIONS = (
    {
        "key": "dashboard",
        "name": "首页看板",
        "description": "查看系统运行概览与相关状态。",
    },
    {
        "key": "listener_tasks",
        "name": "监听任务",
        "description": "查看和管理监听任务与规则。",
        "requires": ("accounts", "bots"),
    },
    {
        "key": "clone_tasks",
        "name": "克隆任务",
        "description": "查看和管理历史克隆任务。",
        "requires": ("accounts", "bots"),
    },
    {
        "key": "bots",
        "name": "Bot 管理",
        "description": "查看和管理分发 Bot 及公开资料。",
    },
    {
        "key": "channels",
        "name": "频道管理",
        "description": "查看和管理频道、搜索机器人及收录记录。",
    },
    {
        "key": "bulk_replace",
        "name": "批量替换",
        "description": "预览并执行已发送内容的批量替换。",
    },
    {
        "key": "support",
        "name": "客服机器人",
        "description": "查看和管理客服机器人、会话与客户资料。",
    },
    {
        "key": "accounts",
        "name": "账号管理",
        "description": "查看和管理 Telegram 用户账号。",
    },
    {
        "key": "notifications",
        "name": "消息通知",
        "description": "查看和管理账号通知配置。",
        "requires": ("accounts",),
    },
    {
        "key": "alerts",
        "name": "系统告警",
        "description": "查看和处理系统告警。",
    },
    {
        "key": "ai_settings",
        "name": "AI 配置",
        "description": "查看和管理 AI 配置及提示词。",
    },
    {
        "key": "system_settings",
        "name": "系统设置",
        "description": "查看和管理发送设置及公共内容模板。",
    },
)

FEATURE_KEYS = frozenset(item["key"] for item in FEATURE_DEFINITIONS)
FEATURE_ORDER = tuple(item["key"] for item in FEATURE_DEFINITIONS)
FEATURE_DEPENDENCIES = {
    item["key"]: tuple(item.get("requires") or ())
    for item in FEATURE_DEFINITIONS
}

PLAN_FREE = "free"
PLAN_PAID = "paid"
PLAN_KEYS = frozenset({PLAN_FREE, PLAN_PAID})
DEFAULT_FREE_ADVERTISEMENT_TEXT = "本消息由 Telegram 运营系统免费版自动发送。"
DEFAULT_ADVERTISEMENT_SEND_TIME = "12:00"

PLAN_FEATURES = {
    PLAN_FREE: (
        "dashboard",
        "listener_tasks",
        "clone_tasks",
        "bots",
        "accounts",
    ),
    PLAN_PAID: tuple(
        key
        for key in FEATURE_ORDER
        if key not in {"bulk_replace", "support", "notifications", "alerts"}
    ),
}

PLAN_DEFINITIONS = (
    {
        "key": PLAN_FREE,
        "name": "免费版",
        "description": "开放监听、克隆、账号与 Bot；内容保持原样，每日强制发送一次广告。",
        "feature_keys": PLAN_FEATURES[PLAN_FREE],
        "advertisement_required": True,
        "content_processing_enabled": False,
    },
    {
        "key": PLAN_PAID,
        "name": "付费版",
        "description": "开放主要运营功能和内容处理，不开放批量替换、客服、消息通知与系统告警。",
        "feature_keys": PLAN_FEATURES[PLAN_PAID],
        "advertisement_required": False,
        "content_processing_enabled": True,
    },
)

FREE_PLAN_TASK_OVERRIDES = {
    "blocked_keywords": "[]",
    "listen_required_keywords": "[]",
    "replace_words": "{}",
    "footer": "",
    "remove_contact_lines": False,
    "filter_qr_code": False,
    "ai_rewrite_enabled": False,
    "ai_rewrite_provider": "grok",
    "ai_rewrite_model": "",
    "ai_rewrite_prompt": "",
    "ai_prompt_template_id": None,
    "ai_prompt_mode": "fixed",
    "ai_rewrite_max_chars": 800,
    "ai_rewrite_ratio": 0,
    "ai_rewrite_failure_mode": "fallback",
    "use_random_head": False,
    "use_random_body": False,
    "use_random_footer": False,
    "footer_leading_blank_line": False,
    "selected_head_template_group_id": None,
    "selected_body_template_group_id": None,
    "selected_footer_template_group_id": None,
    "selected_filter_template_group_id": None,
    "selected_link_template_group_id": None,
    "selected_contact_template_group_id": None,
    "selected_head_template_id": None,
    "selected_body_template_id": None,
    "selected_footer_template_id": None,
}


def normalize_plan_tier(value, *, strict=False):
    plan_tier = str(value or PLAN_FREE).strip().lower()
    if plan_tier in PLAN_KEYS:
        return plan_tier
    if strict:
        raise ValueError("版本只能是 free 或 paid")
    return PLAN_FREE


def plan_feature_keys(plan_tier):
    return list(PLAN_FEATURES[normalize_plan_tier(plan_tier)])


def plan_content_processing_enabled(plan_tier):
    return normalize_plan_tier(plan_tier) == PLAN_PAID


def apply_plan_task_constraints(values, plan_tier):
    constrained = dict(values or {})
    if normalize_plan_tier(plan_tier) == PLAN_FREE:
        constrained.update(FREE_PLAN_TASK_OVERRIDES)
    return constrained


def normalize_feature_keys(values, *, strict=False):
    """Return known feature keys in the stable UI order.

    Persisted malformed or legacy data must fail closed. API payload validation
    can opt into strict mode so an administrator gets an actionable error.
    """
    if values is None:
        values = []
    if not isinstance(values, (list, tuple, set, frozenset)):
        if strict:
            raise ValueError("功能权限必须是列表")
        return []

    requested = set()
    unknown = set()
    for value in values:
        if not isinstance(value, str):
            if strict:
                raise ValueError("功能权限只能包含字符串")
            continue
        key = value.strip()
        if key in FEATURE_KEYS:
            requested.add(key)
        elif key:
            unknown.add(key)

    if strict and unknown:
        raise ValueError(f"未知功能权限：{', '.join(sorted(unknown))}")

    return [key for key in FEATURE_ORDER if key in requested]


def expand_feature_dependencies(values, *, strict=False):
    """Expand an administrator's intended grants to a usable permission set."""
    expanded = set(normalize_feature_keys(values, strict=strict))
    pending = list(expanded)
    while pending:
        feature_key = pending.pop()
        for dependency_key in FEATURE_DEPENDENCIES.get(feature_key, ()):
            if dependency_key not in expanded:
                expanded.add(dependency_key)
                pending.append(dependency_key)
    return [key for key in FEATURE_ORDER if key in expanded]


def enforce_feature_dependencies(values):
    """Fail closed when legacy persisted grants omit required permissions."""
    effective = set(normalize_feature_keys(values))
    changed = True
    while changed:
        changed = False
        for feature_key in tuple(effective):
            required = FEATURE_DEPENDENCIES.get(feature_key, ())
            if any(dependency_key not in effective for dependency_key in required):
                effective.remove(feature_key)
                changed = True
    return [key for key in FEATURE_ORDER if key in effective]


def parse_feature_keys_json(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return normalize_feature_keys(parsed)


def dump_feature_keys_json(values):
    return json.dumps(
        expand_feature_dependencies(values, strict=True),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def utc_datetime_text(value):
    normalized = normalize_utc_datetime(value)
    if normalized is None:
        return None
    return normalized.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def effective_feature_keys(role, persisted_value, plan_tier=None):
    if str(role or "").strip().lower() == "admin":
        return list(FEATURE_ORDER)
    if plan_tier is not None:
        return plan_feature_keys(plan_tier)
    return enforce_feature_dependencies(parse_feature_keys_json(persisted_value))


def access_summary(*, role, status, feature_keys, access_expires_at, now=None):
    normalized_role = str(role or "").strip().lower()
    normalized_status = str(status or "").strip().lower()
    expires_at = normalize_utc_datetime(access_expires_at)
    current_time = normalize_utc_datetime(now) or datetime.utcnow()

    if normalized_status != "active":
        state = "disabled"
        available = False
    elif normalized_role == "admin":
        state = "active"
        available = True
        expires_at = None
    elif expires_at is not None and expires_at <= current_time:
        state = "expired"
        available = False
    elif not feature_keys:
        state = "pending"
        available = False
    else:
        state = "active"
        available = True

    return {
        "access_state": state,
        "access_expires_at": utc_datetime_text(expires_at),
        "available": available,
    }


def user_has_feature(user, feature_key):
    if isinstance(user, dict):
        role = user.get("role")
        feature_keys = enforce_feature_dependencies(user.get("feature_keys") or [])
    else:
        role = getattr(user, "role", "")
        feature_keys = effective_feature_keys(
            role,
            getattr(user, "feature_keys_json", "[]"),
            getattr(user, "plan_tier", None),
        )
    return str(role or "").strip().lower() == "admin" or feature_key in feature_keys
