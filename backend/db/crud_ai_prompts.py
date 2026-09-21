from datetime import datetime

from auth.tenant import current_tenant_user_id
from db.database import SessionLocal
from db.models import AiPromptTemplate, CloneTask, ListenerTask, SystemSetting
from db.crud_settings import DEFAULT_AI_REWRITE_PROMPT


DEFAULT_PROMPT_NAME = "系统默认提示词"


def _normalize_content_type(value):
    from bot.ai_prompt_routing import CONTENT_TYPES
    value = str(value or "").strip()
    if value and value not in CONTENT_TYPES:
        raise ValueError("不支持的文案类型")
    return value


def get_routing_prompts(owner_user_id=None):
    """Latest enabled template per category, strictly within the current owner."""
    db = SessionLocal()
    try:
        prompts = _prompt_query(db, owner_user_id).filter(
            AiPromptTemplate.enabled == True,
            AiPromptTemplate.content_type != "",
        ).order_by(AiPromptTemplate.updated_at.desc(), AiPromptTemplate.id.desc()).all()
        result = {}
        for prompt in prompts:
            if prompt.content_type not in result and str(prompt.content or "").strip():
                result[prompt.content_type] = {
                    "id": prompt.id, "name": prompt.name, "content": prompt.content,
                }
        return result
    finally:
        db.close()


def _resolve_owner_user_id(owner_user_id=None):
    if owner_user_id not in (None, ""):
        return int(owner_user_id)
    return current_tenant_user_id()


def _prompt_query(db, owner_user_id=None):
    owner_user_id = _resolve_owner_user_id(owner_user_id)
    query = db.query(AiPromptTemplate)
    if owner_user_id is None:
        return query.filter(AiPromptTemplate.owner_user_id.is_(None))
    return query.filter(AiPromptTemplate.owner_user_id == owner_user_id)


def _normalize_name(value):
    name = str(value or "").strip()
    if not name:
        raise ValueError("提示词名称不能为空")
    if len(name) > 100:
        raise ValueError("提示词名称不能超过 100 个字符")
    return name


def _normalize_content(value):
    content = str(value or "").strip()
    if not content:
        raise ValueError("提示词内容不能为空")
    if len(content) > 20000:
        raise ValueError("提示词内容不能超过 20000 个字符")
    return content


def _legacy_default_content(db, owner_user_id=None):
    owner_user_id = _resolve_owner_user_id(owner_user_id)
    setting_query = db.query(SystemSetting).filter(
        SystemSetting.key == "ai_default_rewrite_prompt"
    )
    if owner_user_id is None:
        setting_query = setting_query.filter(SystemSetting.owner_user_id.is_(None))
    else:
        setting_query = setting_query.filter(SystemSetting.owner_user_id == owner_user_id)
    setting = setting_query.first()
    return str(getattr(setting, "value", "") or "").strip() or DEFAULT_AI_REWRITE_PROMPT


def ensure_default_ai_prompt(db=None, owner_user_id=None):
    owns_session = db is None
    session = db or SessionLocal()
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    try:
        if resolved_owner_user_id is None and session.query(AiPromptTemplate.id).first() is not None:
            return _prompt_query(session, None).order_by(AiPromptTemplate.id.asc()).first()
        default_prompt = _prompt_query(session, resolved_owner_user_id).filter(
            AiPromptTemplate.is_default == True
        ).order_by(AiPromptTemplate.id.asc()).first()
        if default_prompt:
            if not default_prompt.enabled:
                default_prompt.enabled = True
                default_prompt.updated_at = datetime.utcnow()
                session.commit()
            return default_prompt

        first_prompt = _prompt_query(session, resolved_owner_user_id).order_by(
            AiPromptTemplate.id.asc()
        ).first()
        if first_prompt:
            first_prompt.is_default = True
            first_prompt.enabled = True
            first_prompt.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(first_prompt)
            return first_prompt

        default_prompt = AiPromptTemplate(
            owner_user_id=resolved_owner_user_id,
            name=DEFAULT_PROMPT_NAME,
            content=_legacy_default_content(session, resolved_owner_user_id),
            is_default=True,
            enabled=True,
        )
        session.add(default_prompt)
        session.commit()
        session.refresh(default_prompt)
        return default_prompt
    finally:
        if owns_session:
            session.close()


def _usage_counts(db, prompt_id, owner_user_id=None):
    owner_user_id = _resolve_owner_user_id(owner_user_id)
    clone_count = db.query(CloneTask).filter(
        CloneTask.ai_prompt_template_id == prompt_id
    )
    listener_count = db.query(ListenerTask).filter(
        ListenerTask.ai_prompt_template_id == prompt_id
    )
    if owner_user_id is None:
        clone_count = clone_count.filter(CloneTask.owner_user_id.is_(None))
        listener_count = listener_count.filter(ListenerTask.owner_user_id.is_(None))
    else:
        clone_count = clone_count.filter(CloneTask.owner_user_id == owner_user_id)
        listener_count = listener_count.filter(ListenerTask.owner_user_id == owner_user_id)
    return clone_count.count(), listener_count.count()


def prompt_to_dict(prompt, db=None, owner_user_id=None):
    owns_session = db is None
    session = db or SessionLocal()
    try:
        clone_count, listener_count = _usage_counts(session, prompt.id, owner_user_id or prompt.owner_user_id)
        return {
            "id": prompt.id,
            "name": prompt.name,
            "content": prompt.content,
            "content_type": prompt.content_type or "",
            "is_default": bool(prompt.is_default),
            "enabled": bool(prompt.enabled),
            "clone_task_count": clone_count,
            "listener_task_count": listener_count,
            "usage_count": clone_count + listener_count,
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
        }
    finally:
        if owns_session:
            session.close()


def list_ai_prompts(owner_user_id=None):
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    db = SessionLocal()
    try:
        ensure_default_ai_prompt(db, resolved_owner_user_id)
        prompts = _prompt_query(db, resolved_owner_user_id).order_by(
            AiPromptTemplate.is_default.desc(),
            AiPromptTemplate.enabled.desc(),
            AiPromptTemplate.updated_at.desc(),
            AiPromptTemplate.id.desc(),
        ).all()
        return [prompt_to_dict(prompt, db, resolved_owner_user_id) for prompt in prompts]
    finally:
        db.close()


def get_ai_prompt(prompt_id, owner_user_id=None):
    if prompt_id in (None, "", 0):
        return None
    db = SessionLocal()
    try:
        return _prompt_query(db, owner_user_id).filter(
            AiPromptTemplate.id == int(prompt_id)
        ).first()
    finally:
        db.close()


def create_ai_prompt(data, owner_user_id=None):
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    db = SessionLocal()
    try:
        name = _normalize_name(data.get("name"))
        content = _normalize_content(data.get("content"))
        if _prompt_query(db, resolved_owner_user_id).filter(AiPromptTemplate.name == name).first():
            raise ValueError("提示词名称已存在")

        make_default = bool(data.get("is_default"))
        if make_default:
            _prompt_query(db, resolved_owner_user_id).update({"is_default": False})

        prompt = AiPromptTemplate(
            owner_user_id=resolved_owner_user_id,
            name=name,
            content=content,
            content_type=_normalize_content_type(data.get("content_type")),
            is_default=make_default,
            enabled=True if make_default else bool(data.get("enabled", True)),
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        if not _prompt_query(db, resolved_owner_user_id).filter(
            AiPromptTemplate.is_default == True
        ).first():
            prompt.is_default = True
            prompt.enabled = True
            db.commit()
            db.refresh(prompt)
        return prompt_to_dict(prompt, db, resolved_owner_user_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_ai_prompt(prompt_id, data, owner_user_id=None):
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    db = SessionLocal()
    try:
        prompt = _prompt_query(db, resolved_owner_user_id).filter(
            AiPromptTemplate.id == int(prompt_id)
        ).first()
        if not prompt:
            raise LookupError("提示词不存在")

        if "name" in data and data.get("name") is not None:
            name = _normalize_name(data.get("name"))
            duplicate = _prompt_query(db, resolved_owner_user_id).filter(
                AiPromptTemplate.name == name,
                AiPromptTemplate.id != prompt.id,
            ).first()
            if duplicate:
                raise ValueError("提示词名称已存在")
            prompt.name = name

        if "content_type" in data and data.get("content_type") is not None:
            prompt.content_type = _normalize_content_type(data["content_type"])

        if "content" in data and data.get("content") is not None:
            prompt.content = _normalize_content(data.get("content"))

        if "enabled" in data and data.get("enabled") is not None:
            enabled = bool(data.get("enabled"))
            if prompt.is_default and not enabled:
                raise ValueError("系统默认提示词不能停用，请先设置其他默认提示词")
            prompt.enabled = enabled

        if bool(data.get("is_default")):
            _prompt_query(db, resolved_owner_user_id).filter(
                AiPromptTemplate.id != prompt.id
            ).update({"is_default": False})
            prompt.is_default = True
            prompt.enabled = True

        prompt.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(prompt)
        return prompt_to_dict(prompt, db, resolved_owner_user_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_default_ai_prompt(prompt_id, owner_user_id=None):
    return update_ai_prompt(
        prompt_id,
        {"is_default": True, "enabled": True},
        owner_user_id=owner_user_id,
    )


def delete_ai_prompt(prompt_id, owner_user_id=None):
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    db = SessionLocal()
    try:
        prompt = _prompt_query(db, resolved_owner_user_id).filter(
            AiPromptTemplate.id == int(prompt_id)
        ).first()
        if not prompt:
            raise LookupError("提示词不存在")
        if prompt.is_default:
            raise ValueError("系统默认提示词不能删除，请先设置其他默认提示词")

        clone_count, listener_count = _usage_counts(db, prompt.id, resolved_owner_user_id)
        if clone_count or listener_count:
            raise ValueError(
                f"该提示词正在被 {clone_count + listener_count} 个任务使用，无法删除"
            )

        db.delete(prompt)
        db.commit()
        return {"ok": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_prompt_content_for_task(prompt_id=None, legacy_prompt="", owner_user_id=None):
    resolved_owner_user_id = _resolve_owner_user_id(owner_user_id)
    db = SessionLocal()
    try:
        if prompt_id not in (None, "", 0):
            try:
                selected = _prompt_query(db, resolved_owner_user_id).filter(
                    AiPromptTemplate.id == int(prompt_id),
                    AiPromptTemplate.enabled == True,
                ).first()
            except (TypeError, ValueError):
                selected = None
            if selected and str(selected.content or "").strip():
                return selected.content.strip()

        legacy = str(legacy_prompt or "").strip()
        if legacy:
            return legacy

        default_prompt = ensure_default_ai_prompt(db, resolved_owner_user_id)
        return str(default_prompt.content or DEFAULT_AI_REWRITE_PROMPT).strip()
    finally:
        db.close()


def get_default_ai_prompt_content(owner_user_id=None):
    return get_prompt_content_for_task(owner_user_id=owner_user_id)
