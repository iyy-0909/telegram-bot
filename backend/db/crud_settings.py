from datetime import datetime

from db.database import SessionLocal
from db.models import SystemSetting


DEFAULT_SEND_SETTINGS = {
    "global_send_delay": 3,
    "send_retry_count": 2,
    "send_retry_delay": 5,
}

AI_PROVIDERS = {
    "grok": {"default_model": "grok-4.6"},
    "deepseek": {"default_model": "deepseek-v4-flash"},
}

DEFAULT_AI_REWRITE_PROMPT = """你是一名专业的 Telegram 频道中文文案编辑。请理解输入内容，在保持事实准确的前提下重新创作，并输出可直接发布的 Telegram HTML 正文。

系统会在调用 AI 前根据任务配置完成基础清理。清理后仍然存在的联系方式、Telegram 用户名、微信号、电话号码、网址、频道链接、预约方式和 # 标签，都是需要处理并保留的有效信息，不得擅自删除。

【事实与重写】

1. 必须保留原文明确给出的商家名称、项目、价格、数字、时间、地点、活动规则、风险提示及核心意思。
2. 不得添加原文没有的服务、优惠、地址、时间、成交数量、客户评价、火爆程度或其他具体承诺；不完整的信息不得猜测补全。
3. 先理解信息，再重新设计标题、句式、段落顺序和表达方式；禁止依照原文顺序逐句换词。
4. 除名称、数字、地点和必要专有名词外，避免连续照抄原文超过 8 个汉字；必须明显重写大部分句式。
5. 合并重复内容，删除重复口号和无实际意义的句子。输入排版混乱时必须重新组织，不能沿用原换行。
6. 可以增加约 20%～35% 的标题、过渡、氛围或场景表达，但只能丰富表达，不能丰富事实。
7. 程序会在本提示词后附加“本次指定版式”。必须执行该版式，不得自行换回惯用模板。
8. 不得固定套用“核心亮点、适合场景、营业信息、联系与预约”等标题，也不得反复使用相同开场、收尾和营销套话。

【联系方式】

1. 输入中存在的 @用户名、微信号、电话号码、网址、频道链接、预约方式和联系人必须全部原样保留。
2. 禁止删除、隐藏、脱敏、缩写、改写或替换；不得修改大小写、数字、下划线、@符号、短横线和链接路径。
3. 可以调整联系方式的位置和排版，但不得把具体账号改成“联系工作人员”等模糊表达。

【表情处理】

1. 会员表情、自定义表情、黑色方块、空白占位和乱码符号应替换为含义相近的普通 Unicode Emoji、项目符号“•”，或直接删除。
2. 用作列表标记的异常表情统一改为“•”；无法判断含义时直接删除，禁止批量替换成笑脸。
3. 连续相同或相近的 Emoji 只保留一个；删除纯表情行和文末表情堆叠。
4. 每段最多一个 Emoji，全文最多三个；原文没有 Emoji 时可按语境少量添加。

【# 标签】

1. 适当保留原文中与商家、城市、服务类型和主题直接相关的标签，不得全部删除。
2. 删除重复、乱码和无关标签；标签过多时保留最相关的 3～5 个。
3. 可以补充最多 1 个高度相关的新标签，但不得编造品牌、地点、项目或优惠。
4. 标签集中放在正文末尾一行，使用一个空格分隔。

【Telegram HTML】

1. 只使用 Telegram 支持的简单 HTML，主要使用 `<b>` 和 `<i>`；标签必须完整闭合。
2. 根据本次指定版式适度使用加粗、斜体、短段落或“•”列表，不得整篇加粗。
3. 禁止使用 Markdown 的 `**加粗**`、代码块、连续横线、下划线或大量空格作为分隔线。
4. 必须输出真实 HTML 标签，禁止输出 `\\<b>`、`&lt;b&gt;` 等转义形式。

【输出协议】

1. 只输出最终正文，不得输出分析、处理说明、原文对照、“以下是结果”或其他附加内容。
2. 若输入没有任何可用于创作的有效文字，只输出 `[[SKIP]]`，不得解释原因。
3. 输出前检查事实、联系方式、标签、表情、HTML 闭合情况以及是否明显重写。
4. 总长度不得超过 {{max_chars}} 个字符。

待处理文本：
{{content}}"""


SETTING_REMARKS = {
    "global_send_delay": "任意两次 Bot API 发送之间的全局最小间隔秒数",
    "send_retry_count": "发送异常时的重试次数，只重试抛异常的发送，不重试业务失败",
    "send_retry_delay": "发送异常重试前等待秒数",
}


def to_non_negative_int(value, fallback):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback

    if number < 0:
        return fallback

    return number


def get_setting(key, default=""):
    db = SessionLocal()

    try:
        setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == key)
            .first()
        )

        if not setting:
            return default

        return setting.value

    finally:
        db.close()


def set_setting(key, value, remark=None):
    db = SessionLocal()

    try:
        setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == key)
            .first()
        )

        if not setting:
            setting = SystemSetting(
                key=key,
                value=str(value),
                remark=remark or SETTING_REMARKS.get(key, ""),
                updated_at=datetime.utcnow(),
            )
            db.add(setting)
        else:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()

            if remark is not None:
                setting.remark = remark

        db.commit()
        db.refresh(setting)
        return setting

    finally:
        db.close()


def ensure_default_settings():
    for key, value in DEFAULT_SEND_SETTINGS.items():
        if get_setting(key, None) is None:
            set_setting(
                key,
                value,
                remark=SETTING_REMARKS.get(key, ""),
            )


def get_send_settings():
    return {
        key: to_non_negative_int(
            get_setting(key, default),
            default,
        )
        for key, default in DEFAULT_SEND_SETTINGS.items()
    }


def update_send_settings(data):
    normalized = {}

    for key, default in DEFAULT_SEND_SETTINGS.items():
        if key in data and data[key] is not None:
            normalized[key] = to_non_negative_int(data[key], default)

    for key, value in normalized.items():
        set_setting(
            key,
            value,
            remark=SETTING_REMARKS.get(key, ""),
        )

    return get_send_settings()


def get_ai_settings():
    """Return UI-safe AI settings. API keys must never be sent to clients."""
    providers = {}
    for name, defaults in AI_PROVIDERS.items():
        providers[name] = {
            "configured": bool((get_setting(f"ai_{name}_api_key", "") or "").strip()),
            "model": (get_setting(f"ai_{name}_model", defaults["default_model"]) or defaults["default_model"]).strip(),
        }
    return {
        "providers": providers,
        "default_rewrite_prompt": get_default_ai_rewrite_prompt(),
    }


def update_ai_settings(data):
    for name, defaults in AI_PROVIDERS.items():
        api_key = data.get(f"{name}_api_key")
        if api_key is not None:
            api_key = str(api_key).strip()
            if api_key:
                set_setting(f"ai_{name}_api_key", api_key, remark=f"{name} AI API key")

        clear_key = bool(data.get(f"clear_{name}_api_key", False))
        if clear_key:
            set_setting(f"ai_{name}_api_key", "", remark=f"{name} AI API key")

        model = data.get(f"{name}_model")
        if model is not None:
            set_setting(
                f"ai_{name}_model",
                str(model).strip() or defaults["default_model"],
                remark=f"{name} AI default model",
            )
    if "default_rewrite_prompt" in data and data["default_rewrite_prompt"] is not None:
        content = str(data["default_rewrite_prompt"]).strip() or DEFAULT_AI_REWRITE_PROMPT
        set_setting(
            "ai_default_rewrite_prompt",
            content,
            remark="AI 内容改写默认提示词",
        )
        from db.crud_ai_prompts import ensure_default_ai_prompt, update_ai_prompt

        default_prompt = ensure_default_ai_prompt()
        update_ai_prompt(default_prompt.id, {"content": content})
    return get_ai_settings()


def get_default_ai_rewrite_prompt():
    from db.crud_ai_prompts import get_default_ai_prompt_content

    return get_default_ai_prompt_content()


def get_ai_provider_config(provider):
    name = (provider or "").strip().lower()
    if name not in AI_PROVIDERS:
        return None
    defaults = AI_PROVIDERS[name]
    return {
        "api_key": (get_setting(f"ai_{name}_api_key", "") or "").strip(),
        "model": (get_setting(f"ai_{name}_model", defaults["default_model"]) or defaults["default_model"]).strip(),
    }
