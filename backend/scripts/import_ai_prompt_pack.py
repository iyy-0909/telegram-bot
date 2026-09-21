"""Safely import one account's categorized AI prompt pack into SQLite.

The command is a dry run unless ``--apply`` is supplied. Existing templates
are matched by their current name or the legacy ``上海频道｜`` name and are
updated in place so task bindings keep the same template id.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


EXPECTED_TYPES = (
    "product",
    "promotion",
    "notice",
    "tutorial",
    "story",
    "general",
)
SYSTEM_DEFAULT_NAME = "系统默认提示词"
COMMON_RULES_KEY = "ai_common_rewrite_rules"
LEGACY_DEFAULT_KEY = "ai_default_rewrite_prompt"


class ImportValidationError(RuntimeError):
    pass


def content_hash(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def load_pack(path):
    pack_path = Path(path).resolve()
    try:
        payload = json.loads(pack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportValidationError(f"无法读取提示词包：{exc}") from exc

    prompts = payload.get("prompts")
    if not isinstance(prompts, list) or len(prompts) != len(EXPECTED_TYPES):
        raise ImportValidationError("提示词包必须恰好包含六类 prompts")

    normalized = []
    seen_types = set()
    seen_names = set()
    for item in prompts:
        if not isinstance(item, dict):
            raise ImportValidationError("prompts 中的每一项都必须是对象")
        name = str(item.get("name") or "").strip()
        content_type = str(item.get("content_type") or "").strip()
        content = str(item.get("content") or "").strip()
        if content_type not in EXPECTED_TYPES:
            raise ImportValidationError(f"不支持的文案类型：{content_type or '<empty>'}")
        if content_type in seen_types:
            raise ImportValidationError(f"文案类型重复：{content_type}")
        if not name or len(name) > 100:
            raise ImportValidationError("提示词名称不能为空且不能超过 100 个字符")
        if name in seen_names:
            raise ImportValidationError(f"提示词名称重复：{name}")
        if not name.startswith("商K｜"):
            raise ImportValidationError(f"多城市商K提示词名称无效：{name}")
        if not content or len(content) > 20000:
            raise ImportValidationError(f"提示词内容为空或超过 20000 字符：{name}")
        if bool(item.get("is_default")):
            raise ImportValidationError(f"分类提示词不能设为系统默认：{name}")
        normalized.append(
            {
                "name": name,
                "legacy_name": name.replace("商K｜", "上海频道｜", 1),
                "content_type": content_type,
                "content": content,
                "enabled": bool(item.get("enabled", True)),
                "is_default": False,
            }
        )
        seen_types.add(content_type)
        seen_names.add(name)

    if seen_types != set(EXPECTED_TYPES):
        missing = ", ".join(sorted(set(EXPECTED_TYPES) - seen_types))
        raise ImportValidationError(f"提示词包缺少文案类型：{missing}")

    common_rules = str(payload.get("common_rules") or "").strip()
    if not common_rules or len(common_rules) > 20000:
        raise ImportValidationError("common_rules 不能为空且不能超过 20000 字符")
    if "{{content}}" in common_rules or "{{analysis}}" in common_rules:
        raise ImportValidationError("common_rules 不能包含 {{content}} 或 {{analysis}}")

    default_prompt = payload.get("default_prompt")
    if not isinstance(default_prompt, dict):
        raise ImportValidationError("提示词包缺少 default_prompt")
    default_name = str(default_prompt.get("name") or "").strip()
    default_content = str(default_prompt.get("content") or "").strip()
    if default_name != SYSTEM_DEFAULT_NAME:
        raise ImportValidationError(f"default_prompt.name 必须为 {SYSTEM_DEFAULT_NAME}")
    if not default_content or len(default_content) > 20000:
        raise ImportValidationError("default_prompt.content 不能为空且不能超过 20000 字符")

    return {
        "path": str(pack_path),
        "target_username": str(payload.get("target_username") or "").strip(),
        "prompts": normalized,
        "common_rules": common_rules,
        "default_prompt": {"name": default_name, "content": default_content},
    }


def resolve_database_path(explicit_path=None):
    if explicit_path:
        return Path(explicit_path).resolve()
    database_url = os.getenv("DATABASE_URL", "sqlite:///data/clonebot.db").strip()
    if not database_url.startswith("sqlite:///"):
        raise ImportValidationError("提示词包导入当前仅支持 SQLite")
    raw_path = unquote(database_url.replace("sqlite:///", "", 1))
    if raw_path in {"", ":memory:"}:
        raise ImportValidationError("提示词包导入需要持久化 SQLite 数据库")
    return Path(raw_path).resolve()


def table_columns(connection, table_name):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not exists:
        return set()
    return {
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def require_schema(connection):
    required = {
        "user_accounts": {"id", "username"},
        "ai_prompt_templates": {
            "id",
            "owner_user_id",
            "name",
            "content",
            "is_default",
            "enabled",
        },
        "system_settings": {"id", "owner_user_id", "key", "value"},
    }
    columns = {}
    for table_name, expected in required.items():
        current = table_columns(connection, table_name)
        missing = expected - current
        if missing:
            raise ImportValidationError(
                f"数据库表 {table_name} 缺少字段：{', '.join(sorted(missing))}"
            )
        columns[table_name] = current
    return columns


def resolve_owner(connection, username):
    normalized = str(username or "").strip().lower()
    if not normalized:
        raise ImportValidationError("必须通过 --username 指定目标账号，或在包中提供 target_username")
    rows = connection.execute(
        "SELECT id, username FROM user_accounts WHERE lower(username)=? ORDER BY id",
        (normalized,),
    ).fetchall()
    if len(rows) != 1:
        raise ImportValidationError(
            f"目标账号 {normalized} 的匹配数量为 {len(rows)}，已拒绝导入"
        )
    return int(rows[0][0]), str(rows[0][1])


def prompt_rows(connection, owner_id, has_content_type):
    content_type_sql = "content_type" if has_content_type else "'' AS content_type"
    return connection.execute(
        "SELECT id, name, content, " + content_type_sql + ", is_default, enabled "
        "FROM ai_prompt_templates WHERE owner_user_id=? ORDER BY id",
        (owner_id,),
    ).fetchall()


def setting_rows(connection, owner_id, key):
    return connection.execute(
        "SELECT id, value FROM system_settings "
        "WHERE owner_user_id=? AND key=? ORDER BY id",
        (owner_id, key),
    ).fetchall()


def task_binding_snapshot(connection, owner_id):
    snapshot = {}
    for table_name in ("clone_tasks", "listener_tasks"):
        columns = table_columns(connection, table_name)
        if not {"id", "ai_prompt_template_id"}.issubset(columns):
            snapshot[table_name] = []
            continue
        if "owner_user_id" in columns:
            rows = connection.execute(
                f'SELECT id, ai_prompt_template_id FROM "{table_name}" '
                "WHERE owner_user_id=? ORDER BY id",
                (owner_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                f'SELECT id, ai_prompt_template_id FROM "{table_name}" ORDER BY id'
            ).fetchall()
        snapshot[table_name] = [[row[0], row[1]] for row in rows]
    return snapshot


def snapshot_hash(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_plan(connection, pack, username, update_system_default):
    columns = require_schema(connection)
    owner_id, resolved_username = resolve_owner(connection, username)
    has_content_type = "content_type" in columns["ai_prompt_templates"]
    existing_prompts = prompt_rows(connection, owner_id, has_content_type)
    by_name = {}
    for row in existing_prompts:
        by_name.setdefault(str(row[1]), []).append(row)

    prompt_plans = []
    matched_ids = set()
    for item in pack["prompts"]:
        matches = by_name.get(item["name"], []) + by_name.get(item["legacy_name"], [])
        matches = {int(row[0]): row for row in matches}
        if len(matches) > 1:
            raise ImportValidationError(
                f"同时存在新旧同类提示词，无法安全合并：{item['name']}"
            )
        row = next(iter(matches.values()), None)
        if row is not None and bool(row[4]):
            raise ImportValidationError(
                f"分类提示词意外成为系统默认，已拒绝修改：{row[1]}"
            )
        expected_hash = content_hash(item["content"])
        if row is None:
            action = "create"
            prompt_id = None
            before_hash = None
        else:
            prompt_id = int(row[0])
            matched_ids.add(prompt_id)
            before_hash = content_hash(row[2])
            exact = (
                str(row[1]) == item["name"]
                and str(row[2]) == item["content"]
                and has_content_type
                and str(row[3] or "") == item["content_type"]
                and not bool(row[4])
                and bool(row[5]) == item["enabled"]
            )
            action = "unchanged" if exact else "update"
        prompt_plans.append(
            {
                **item,
                "id": prompt_id,
                "action": action,
                "before_sha256": before_hash,
                "expected_sha256": expected_hash,
            }
        )

    common_rows = setting_rows(connection, owner_id, COMMON_RULES_KEY)
    if len(common_rows) > 1:
        raise ImportValidationError("同一账号存在多条 ai_common_rewrite_rules，已拒绝导入")
    common_row = common_rows[0] if common_rows else None
    common_action = (
        "create"
        if common_row is None
        else "unchanged"
        if str(common_row[1]) == pack["common_rules"]
        else "update"
    )
    common_plan = {
        "id": int(common_row[0]) if common_row else None,
        "action": common_action,
        "before_sha256": content_hash(common_row[1]) if common_row else None,
        "expected_sha256": content_hash(pack["common_rules"]),
    }

    default_plan = {"requested": bool(update_system_default), "action": "skipped"}
    default_id = None
    if update_system_default:
        defaults = [row for row in existing_prompts if bool(row[4])]
        if len(defaults) != 1:
            raise ImportValidationError(
                f"目标账号系统默认提示词数量为 {len(defaults)}，已拒绝修改"
            )
        default_row = defaults[0]
        if str(default_row[1]) != SYSTEM_DEFAULT_NAME:
            raise ImportValidationError(
                f"当前默认提示词是自定义模板“{default_row[1]}”，已拒绝修改"
            )
        default_id = int(default_row[0])
        expected_default = pack["default_prompt"]["content"]
        legacy_rows = setting_rows(connection, owner_id, LEGACY_DEFAULT_KEY)
        if len(legacy_rows) > 1:
            raise ImportValidationError("同一账号存在多条 ai_default_rewrite_prompt，已拒绝导入")
        legacy_row = legacy_rows[0] if legacy_rows else None
        row_same = str(default_row[2]) == expected_default
        legacy_same = legacy_row is not None and str(legacy_row[1]) == expected_default
        default_plan = {
            "requested": True,
            "id": default_id,
            "action": "unchanged" if row_same and legacy_same else "update",
            "before_sha256": content_hash(default_row[2]),
            "expected_sha256": content_hash(expected_default),
            "legacy_setting_action": (
                "create"
                if legacy_row is None
                else "unchanged"
                if legacy_same
                else "update"
            ),
        }

    protected_prompt_ids = [
        int(row[0])
        for row in existing_prompts
        if int(row[0]) not in matched_ids and int(row[0]) != default_id
    ]
    protected_prompts = [
        list(row)
        for row in existing_prompts
        if int(row[0]) in protected_prompt_ids
    ]
    task_bindings = task_binding_snapshot(connection, owner_id)
    source_state = {
        "prompts": [list(row) for row in existing_prompts],
        "common_rules": [list(row) for row in common_rows],
        "legacy_default": [
            list(row) for row in setting_rows(connection, owner_id, LEGACY_DEFAULT_KEY)
        ],
        "task_bindings": task_bindings,
    }
    changed = (
        not has_content_type
        or any(item["action"] != "unchanged" for item in prompt_plans)
        or common_action != "unchanged"
        or default_plan["action"] not in {"skipped", "unchanged"}
    )
    return {
        "owner_id": owner_id,
        "username": resolved_username,
        "schema_changes": [] if has_content_type else ["ai_prompt_templates.content_type"],
        "prompts": prompt_plans,
        "common_rules": common_plan,
        "system_default": default_plan,
        "protected_prompt_ids": protected_prompt_ids,
        "protected_prompts_sha256": snapshot_hash(protected_prompts),
        "task_bindings_sha256": snapshot_hash(task_bindings),
        "source_state_sha256": snapshot_hash(source_state),
        "task_binding_counts": {
            table: len(rows) for table, rows in task_bindings.items()
        },
        "changed": changed,
    }


def create_backup(connection, database_path):
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"{database_path.name}.before-ai-prompt-pack-{stamp}.db"
    target = sqlite3.connect(backup_path)
    try:
        connection.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ImportValidationError(f"数据库备份完整性检查失败：{integrity}")
    finally:
        target.close()
    return backup_path


def set_setting(connection, columns, owner_id, key, value, remark, timestamp):
    rows = setting_rows(connection, owner_id, key)
    if len(rows) > 1:
        raise ImportValidationError(f"同一账号存在多条 {key}，已拒绝写入")
    if rows:
        fields = ["value=?"]
        values = [value]
        if "remark" in columns:
            fields.append("remark=?")
            values.append(remark)
        if "updated_at" in columns:
            fields.append("updated_at=?")
            values.append(timestamp)
        values.append(int(rows[0][0]))
        connection.execute(
            f"UPDATE system_settings SET {', '.join(fields)} WHERE id=?",
            values,
        )
        return int(rows[0][0])

    fields = ["owner_user_id", "key", "value"]
    values = [owner_id, key, value]
    if "remark" in columns:
        fields.append("remark")
        values.append(remark)
    if "updated_at" in columns:
        fields.append("updated_at")
        values.append(timestamp)
    placeholders = ", ".join("?" for _ in fields)
    cursor = connection.execute(
        f"INSERT INTO system_settings ({', '.join(fields)}) VALUES ({placeholders})",
        values,
    )
    return int(cursor.lastrowid)


def apply_changes(connection, pack, plan, update_system_default):
    prompt_columns = table_columns(connection, "ai_prompt_templates")
    setting_columns = table_columns(connection, "system_settings")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    owner_id = plan["owner_id"]

    for item in plan["prompts"]:
        if item["action"] == "unchanged":
            continue
        if item["action"] == "update":
            fields = [
                "name=?",
                "content=?",
                "content_type=?",
                "enabled=?",
                "is_default=0",
            ]
            values = [
                item["name"],
                item["content"],
                item["content_type"],
                int(item["enabled"]),
            ]
            if "updated_at" in prompt_columns:
                fields.append("updated_at=?")
                values.append(timestamp)
            values.extend([item["id"], owner_id])
            connection.execute(
                f"UPDATE ai_prompt_templates SET {', '.join(fields)} "
                "WHERE id=? AND owner_user_id=?",
                values,
            )
            continue

        fields = [
            "owner_user_id",
            "name",
            "content",
            "content_type",
            "is_default",
            "enabled",
        ]
        values = [
            owner_id,
            item["name"],
            item["content"],
            item["content_type"],
            0,
            int(item["enabled"]),
        ]
        if "created_at" in prompt_columns:
            fields.append("created_at")
            values.append(timestamp)
        if "updated_at" in prompt_columns:
            fields.append("updated_at")
            values.append(timestamp)
        placeholders = ", ".join("?" for _ in fields)
        connection.execute(
            f"INSERT INTO ai_prompt_templates ({', '.join(fields)}) VALUES ({placeholders})",
            values,
        )

    if plan["common_rules"]["action"] != "unchanged":
        set_setting(
            connection,
            setting_columns,
            owner_id,
            COMMON_RULES_KEY,
            pack["common_rules"],
            "所有 AI 改写共用的事实、联系方式及格式规则",
            timestamp,
        )

    if update_system_default and plan["system_default"]["action"] == "update":
        fields = ["content=?"]
        values = [pack["default_prompt"]["content"]]
        if "updated_at" in prompt_columns:
            fields.append("updated_at=?")
            values.append(timestamp)
        values.extend([plan["system_default"]["id"], owner_id])
        connection.execute(
            f"UPDATE ai_prompt_templates SET {', '.join(fields)} "
            "WHERE id=? AND owner_user_id=?",
            values,
        )
        set_setting(
            connection,
            setting_columns,
            owner_id,
            LEGACY_DEFAULT_KEY,
            pack["default_prompt"]["content"],
            "AI 内容改写默认提示词",
            timestamp,
        )


def verify_result(connection, pack, plan, update_system_default):
    owner_id = plan["owner_id"]
    rows = prompt_rows(connection, owner_id, True)
    by_name = {str(row[1]): row for row in rows}
    for item in pack["prompts"]:
        row = by_name.get(item["name"])
        if row is None:
            raise ImportValidationError(f"导入校验失败，缺少提示词：{item['name']}")
        if (
            str(row[2]) != item["content"]
            or str(row[3] or "") != item["content_type"]
            or bool(row[4])
            or bool(row[5]) != item["enabled"]
            or content_hash(row[2]) != content_hash(item["content"])
        ):
            raise ImportValidationError(f"导入校验失败，提示词不一致：{item['name']}")

    common_rows = setting_rows(connection, owner_id, COMMON_RULES_KEY)
    if len(common_rows) != 1 or str(common_rows[0][1]) != pack["common_rules"]:
        raise ImportValidationError("导入校验失败，common_rules 不一致或数量不是一条")

    if update_system_default:
        default_rows = [row for row in rows if bool(row[4])]
        if (
            len(default_rows) != 1
            or int(default_rows[0][0]) != int(plan["system_default"]["id"])
            or str(default_rows[0][1]) != SYSTEM_DEFAULT_NAME
            or str(default_rows[0][2]) != pack["default_prompt"]["content"]
        ):
            raise ImportValidationError("导入校验失败，系统默认提示词不一致")
        legacy_rows = setting_rows(connection, owner_id, LEGACY_DEFAULT_KEY)
        if len(legacy_rows) != 1 or str(legacy_rows[0][1]) != pack["default_prompt"]["content"]:
            raise ImportValidationError("导入校验失败，默认提示词兼容设置不一致")

    protected = [
        list(row) for row in rows if int(row[0]) in set(plan["protected_prompt_ids"])
    ]
    if snapshot_hash(protected) != plan["protected_prompts_sha256"]:
        raise ImportValidationError("导入校验失败，其他自定义提示词发生变化")
    bindings = task_binding_snapshot(connection, owner_id)
    if snapshot_hash(bindings) != plan["task_bindings_sha256"]:
        raise ImportValidationError("导入校验失败，任务提示词绑定发生变化")


def public_plan(plan):
    return {
        "owner_id": plan["owner_id"],
        "username": plan["username"],
        "schema_changes": plan["schema_changes"],
        "prompts": [
            {
                key: item[key]
                for key in (
                    "id",
                    "name",
                    "legacy_name",
                    "content_type",
                    "action",
                    "before_sha256",
                    "expected_sha256",
                )
            }
            for item in plan["prompts"]
        ],
        "common_rules": plan["common_rules"],
        "system_default": plan["system_default"],
        "task_bindings_sha256": plan["task_bindings_sha256"],
        "source_state_sha256": plan["source_state_sha256"],
        "task_binding_counts": plan["task_binding_counts"],
        "changed": plan["changed"],
    }


def import_prompt_pack(
    database_path,
    pack_path,
    username=None,
    *,
    apply=False,
    update_system_default=False,
):
    pack = load_pack(pack_path)
    target_username = str(username or "").strip() or pack["target_username"]
    path = Path(database_path).resolve()
    if not path.is_file():
        raise ImportValidationError(f"SQLite 数据库不存在：{path}")

    connection = sqlite3.connect(path, timeout=30)
    backup_path = None
    try:
        connection.execute("PRAGMA busy_timeout=30000")
        plan = build_plan(connection, pack, target_username, update_system_default)
        result = {
            "ok": True,
            "mode": "apply" if apply else "dry-run",
            "database": str(path),
            "pack": pack["path"],
            "plan": public_plan(plan),
            "backup": None,
            "verified": False,
        }
        if not apply or not plan["changed"]:
            result["verified"] = not plan["changed"]
            return result

        # The service should be stopped before apply. SQLite's backup API gives
        # a consistent pre-change snapshot even if the database uses WAL mode.
        backup_path = create_backup(connection, path)
        result["backup"] = str(backup_path)

        connection.execute("BEGIN IMMEDIATE")
        if "content_type" not in table_columns(connection, "ai_prompt_templates"):
            connection.execute(
                "ALTER TABLE ai_prompt_templates "
                "ADD COLUMN content_type VARCHAR NOT NULL DEFAULT ''"
            )
        locked_plan = build_plan(
            connection,
            pack,
            target_username,
            update_system_default,
        )
        if locked_plan["source_state_sha256"] != plan["source_state_sha256"]:
            raise ImportValidationError("备份期间提示词配置或任务绑定发生变化，请停止服务后重试")
        apply_changes(connection, pack, locked_plan, update_system_default)
        verify_result(connection, pack, locked_plan, update_system_default)
        connection.commit()

        final_plan = build_plan(
            connection,
            pack,
            target_username,
            update_system_default,
        )
        verify_result(connection, pack, locked_plan, update_system_default)
        if final_plan["changed"]:
            raise ImportValidationError("导入完成后仍检测到待写入变更")
        result["plan"] = public_plan(final_plan)
        result["verified"] = True
        return result
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="幂等导入账号级 AI 提示词包")
    parser.add_argument("--pack", required=True, help="提示词包 JSON 路径")
    parser.add_argument(
        "--username",
        default="",
        help="目标账号用户名；显式值优先于包内 target_username",
    )
    parser.add_argument("--database", default="", help="SQLite 文件路径；默认读取 DATABASE_URL")
    parser.add_argument("--apply", action="store_true", help="执行写入；省略时仅预检")
    parser.add_argument(
        "--update-system-default",
        action="store_true",
        help="同时更新名为“系统默认提示词”的默认模板及兼容设置",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = import_prompt_pack(
            resolve_database_path(args.database),
            args.pack,
            args.username,
            apply=args.apply,
            update_system_default=args.update_system_default,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
