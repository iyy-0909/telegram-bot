import random
from datetime import datetime

from db.database import SessionLocal
from db.models import ContentTemplate
from bot.logger import logger


VALID_TEMPLATE_TYPES = {"head", "body", "footer", "filter", "link"}


def normalize_template_type(value):
    value = (value or "").strip().lower()

    if value not in VALID_TEMPLATE_TYPES:
        raise ValueError("invalid template type")

    return value


def normalize_template_data(data):
    normalized = dict(data or {})

    if "type" in normalized:
        normalized["type"] = normalize_template_type(normalized.get("type"))

    if "name" in normalized:
        normalized["name"] = str(normalized.get("name") or "").strip()

    if "content" in normalized:
        normalized["content"] = str(normalized.get("content") or "")

    if "parent_id" in normalized:
        value = normalized.get("parent_id")
        if value in ("", 0):
            normalized["parent_id"] = None
        elif value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = None
            normalized["parent_id"] = value if value and value > 0 else None

    if "weight" in normalized:
        try:
            weight = int(normalized.get("weight") or 1)
        except (TypeError, ValueError):
            weight = 1
        normalized["weight"] = max(weight, 1)

    if "enabled" in normalized:
        normalized["enabled"] = bool(normalized.get("enabled"))

    return normalized


def get_all_templates():
    db = SessionLocal()

    try:
        return db.query(ContentTemplate).order_by(ContentTemplate.id.desc()).all()
    finally:
        db.close()


def get_template_rules():
    db = SessionLocal()

    try:
        groups = (
            db.query(ContentTemplate)
            .filter(ContentTemplate.parent_id.is_(None))
            .order_by(ContentTemplate.id.desc())
            .all()
        )
        group_ids = [group.id for group in groups]

        items_by_group = {group_id: [] for group_id in group_ids}
        if group_ids:
            items = (
                db.query(ContentTemplate)
                .filter(ContentTemplate.parent_id.in_(group_ids))
                .order_by(ContentTemplate.id.asc())
                .all()
            )

            for item in items:
                items_by_group.setdefault(item.parent_id, []).append(item)

        return [
            {
                "group": group,
                "items": items_by_group.get(group.id, []),
            }
            for group in groups
        ]
    finally:
        db.close()


def get_enabled_templates_by_type(template_type: str):
    db = SessionLocal()

    try:
        template_type = normalize_template_type(template_type)
        return (
            db.query(ContentTemplate)
            .filter(
                ContentTemplate.type == template_type,
                ContentTemplate.enabled == True,
            )
            .all()
        )
    finally:
        db.close()


def get_enabled_template_groups_by_type(template_type: str):
    db = SessionLocal()

    try:
        template_type = normalize_template_type(template_type)
        return (
            db.query(ContentTemplate)
            .filter(
                ContentTemplate.type == template_type,
                ContentTemplate.enabled == True,
                ContentTemplate.parent_id.is_(None),
            )
            .all()
        )
    finally:
        db.close()


def get_enabled_template_items_by_group(template_type: str, group_id: int):
    db = SessionLocal()

    try:
        template_type = normalize_template_type(template_type)
        return (
            db.query(ContentTemplate)
            .filter(
                ContentTemplate.type == template_type,
                ContentTemplate.enabled == True,
                ContentTemplate.parent_id == int(group_id),
            )
            .all()
        )
    finally:
        db.close()


def get_template(template_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(ContentTemplate)
            .filter(ContentTemplate.id == template_id)
            .first()
        )
    finally:
        db.close()


def create_template(data: dict):
    db = SessionLocal()

    try:
        normalized = normalize_template_data(data)
        template = ContentTemplate(**normalized)
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    finally:
        db.close()


def normalize_rule_items(items):
    normalized_items = []

    for item in items or []:
        if not isinstance(item, dict):
            continue

        content = str(item.get("content") or "")
        if not content.strip():
            continue

        try:
            weight = int(item.get("weight") or 1)
        except (TypeError, ValueError):
            weight = 1

        item_id = item.get("id")
        if item_id in ("", 0):
            item_id = None
        elif item_id is not None:
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                item_id = None

        normalized_items.append(
            {
                "id": item_id if item_id and item_id > 0 else None,
                "name": str(item.get("name") or "").strip(),
                "content": content,
                "enabled": bool(item.get("enabled", True)),
                "weight": max(weight, 1),
            }
        )

    return normalized_items


def create_template_rule(data: dict):
    db = SessionLocal()

    try:
        rule_type = normalize_template_type(data.get("type"))
        name = str(data.get("name") or "").strip()
        items = normalize_rule_items(data.get("items") or [])

        group = ContentTemplate(
            parent_id=None,
            name=name,
            type=rule_type,
            content="",
            enabled=bool(data.get("enabled", True)),
            weight=1,
        )
        db.add(group)
        db.flush()

        for index, item in enumerate(items, start=1):
            db.add(
                ContentTemplate(
                    parent_id=group.id,
                    name=item["name"] or f"内容 {index}",
                    type=rule_type,
                    content=item["content"],
                    enabled=item["enabled"],
                    weight=item["weight"],
                )
            )

        db.commit()
        db.refresh(group)
        return group
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_template_rule(rule_id: int, data: dict):
    db = SessionLocal()

    try:
        group = (
            db.query(ContentTemplate)
            .filter(
                ContentTemplate.id == rule_id,
                ContentTemplate.parent_id.is_(None),
            )
            .first()
        )

        if not group:
            return None

        if "type" in data and data.get("type") is not None:
            group.type = normalize_template_type(data.get("type"))

        if "name" in data and data.get("name") is not None:
            group.name = str(data.get("name") or "").strip()

        if "enabled" in data and data.get("enabled") is not None:
            group.enabled = bool(data.get("enabled"))

        group.content = ""
        group.updated_at = datetime.utcnow()

        if "items" in data and data.get("items") is not None:
            items = normalize_rule_items(data.get("items") or [])
            existing_items = {
                item.id: item
                for item in db.query(ContentTemplate)
                .filter(ContentTemplate.parent_id == group.id)
                .all()
            }
            keep_ids = set()

            for index, item_data in enumerate(items, start=1):
                item_id = item_data.get("id")
                item = existing_items.get(item_id) if item_id else None

                if item:
                    keep_ids.add(item.id)
                else:
                    item = ContentTemplate(parent_id=group.id)
                    db.add(item)

                item.name = item_data["name"] or f"内容 {index}"
                item.type = group.type
                item.content = item_data["content"]
                item.enabled = item_data["enabled"]
                item.weight = item_data["weight"]
                item.updated_at = datetime.utcnow()

            for item_id, item in existing_items.items():
                if item_id not in keep_ids:
                    db.delete(item)

        else:
            db.query(ContentTemplate).filter(
                ContentTemplate.parent_id == group.id
            ).update(
                {
                    ContentTemplate.type: group.type,
                    ContentTemplate.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )

        db.commit()
        db.refresh(group)
        return group
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_template(template_id: int, data: dict):
    db = SessionLocal()

    try:
        template = (
            db.query(ContentTemplate)
            .filter(ContentTemplate.id == template_id)
            .first()
        )

        if not template:
            return None

        normalized = normalize_template_data(data)

        for key, value in normalized.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
        return template
    finally:
        db.close()


def delete_template(template_id: int):
    db = SessionLocal()

    try:
        template = (
            db.query(ContentTemplate)
            .filter(ContentTemplate.id == template_id)
            .first()
        )

        if not template:
            return False

        if template.parent_id is None:
            db.query(ContentTemplate).filter(
                ContentTemplate.parent_id == template.id
            ).delete(synchronize_session=False)

        db.delete(template)
        db.commit()
        return True
    finally:
        db.close()


def delete_template_rule(rule_id: int):
    return delete_template(rule_id)


def pick_template_content(
    template_type: str,
    selected_template_id=None,
    selected_group_id=None,
):
    template_type = normalize_template_type(template_type)

    try:
        if selected_template_id:
            template = get_template(int(selected_template_id))

            if not template:
                logger.warning(
                    f"指定内容模板不存在，跳过 | type={template_type} | "
                    f"template_id={selected_template_id}"
                )
                return ""

            if not template.enabled or template.type != template_type:
                logger.warning(
                    f"指定内容模板不可用或类型不匹配，跳过 | type={template_type} | "
                    f"template_id={selected_template_id} | "
                    f"template_type={template.type} | enabled={template.enabled}"
                )
                return ""

            if selected_group_id and template.parent_id != int(selected_group_id):
                logger.warning(
                    f"指定内容模板不属于所选规则，跳过 | type={template_type} | "
                    f"group_id={selected_group_id} | template_id={selected_template_id} | "
                    f"template_parent_id={template.parent_id}"
                )
                return ""

            content = (template.content or "").strip()
            return content

        if selected_group_id:
            group = get_template(int(selected_group_id))

            if not group:
                logger.warning(
                    f"指定内容模板规则不存在，跳过 | type={template_type} | "
                    f"group_id={selected_group_id}"
                )
                return ""

            if not group.enabled or group.type != template_type or group.parent_id is not None:
                logger.warning(
                    f"指定内容模板规则不可用或类型不匹配，跳过 | type={template_type} | "
                    f"group_id={selected_group_id} | group_type={group.type} | "
                    f"enabled={group.enabled} | parent_id={group.parent_id}"
                )
                return ""

            templates = [
                template
                for template in get_enabled_template_items_by_group(
                    template_type,
                    int(selected_group_id),
                )
                if (template.content or "").strip()
            ]
        else:
            templates = [
                template
                for template in get_enabled_templates_by_type(template_type)
                if template.parent_id is not None and (template.content or "").strip()
            ]

            if not templates:
                templates = [
                    template
                    for template in get_enabled_templates_by_type(template_type)
                    if (template.content or "").strip()
                ]

        if not templates:
            return ""

        weights = [max(int(template.weight or 1), 1) for template in templates]
        template = random.choices(templates, weights=weights, k=1)[0]
        return (template.content or "").strip()

    except Exception as e:
        logger.warning(
            f"读取随机内容模板失败，跳过 | type={template_type} | {e}"
        )
        return ""


def get_filter_keywords(selected_group_id=None):
    if not selected_group_id:
        return []

    try:
        group = get_template(int(selected_group_id))

        if (
            not group
            or not group.enabled
            or group.type != "filter"
            or group.parent_id is not None
        ):
            logger.warning(
                f"指定过滤关键词规则不可用，跳过 | group_id={selected_group_id}"
            )
            return []

        items = get_enabled_template_items_by_group("filter", int(selected_group_id))
        keywords = []

        for item in items:
            for line in (item.content or "").splitlines():
                keyword = line.strip()
                if keyword:
                    keywords.append(keyword)

        return keywords
    except Exception as e:
        logger.warning(f"读取过滤关键词规则失败，跳过 | group_id={selected_group_id} | {e}")
        return []
