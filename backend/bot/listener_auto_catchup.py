import copy
import json

from bot.listener_catchup import (
    MAX_AUTO_CATCHUP_ITEMS,
    build_listener_catchup_plan,
    get_message_text,
)
from bot.logger import logger
from bot.sender import cleanup_prepared, prepare_album, prepare_single_message


async def catchup_latest_listener_message(task, force=True, limit=MAX_AUTO_CATCHUP_ITEMS):
    plan = await build_listener_catchup_plan(task, limit=limit or MAX_AUTO_CATCHUP_ITEMS)

    if not plan.get("ok"):
        return plan

    content_items = plan.get("_pending_items") or []

    if not content_items:
        return {
            "ok": True,
            "message": "未检测到需要补齐的内容",
            "requested": limit,
            "processed": 0,
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "targets": plan.get("targets", []),
            "results": [],
        }

    from bot.handlers import send_prepared_to_tasks

    requested_limit = max(min(int(limit or MAX_AUTO_CATCHUP_ITEMS), MAX_AUTO_CATCHUP_ITEMS), 1)
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    results = []
    force_send = False

    for item in content_items:
        messages = item["_messages"]
        source_message_id = item["source_message_id"]
        grouped_id = item["_grouped_id"]
        needed_targets = item["targets"]
        prepared = None
        raw_text = ""

        for message in messages:
            text = get_message_text(message)
            if text:
                raw_text = text
                break

        try:
            if grouped_id and len(messages) > 1:
                prepared = await prepare_album(messages, raw_text)
                source_payload = messages
            else:
                prepared = await prepare_single_message(messages[-1], raw_text)
                source_payload = messages[-1]

            if not prepared or not prepared.get("ok"):
                failed_count += 1
                results.append({
                    "source_message_id": source_message_id,
                    "grouped_id": str(grouped_id) if grouped_id else None,
                    "targets": needed_targets,
                    "ok": False,
                    "message": "内容准备失败，未发送",
                })
                continue

            prepared["_raw_text"] = raw_text
            prepared["_source_payload"] = source_payload

            catchup_task = copy.copy(task)
            catchup_task.target_channels = json.dumps(
                needed_targets,
                ensure_ascii=False,
            )

            sent = await send_prepared_to_tasks(
                prepared=prepared,
                tasks=[catchup_task],
                source_message_id=source_message_id,
                grouped_id=grouped_id,
                force=force_send,
                queue_source_type="listener_catchup",
                queue_reason="监听补齐等待全局限流",
            )

            if sent:
                sent_count += 1
            else:
                skipped_count += 1

            results.append({
                "source_message_id": source_message_id,
                "grouped_id": str(grouped_id) if grouped_id else None,
                "targets": needed_targets,
                "ok": bool(sent),
                "message": "已补齐发送" if sent else "未发送，可能已去重、发送失败或内容被过滤",
            })

        except Exception as e:
            failed_count += 1
            logger.exception(
                f"listener catchup failed | task_id={task.id} | "
                f"source_message_id={source_message_id} | {e}"
            )
            results.append({
                "source_message_id": source_message_id,
                "grouped_id": str(grouped_id) if grouped_id else None,
                "targets": needed_targets,
                "ok": False,
                "message": f"补齐失败：{e}",
            })

        finally:
            if prepared:
                cleanup_prepared(prepared)

    return {
        "ok": failed_count == 0,
        "message": (
            f"补齐完成：成功 {sent_count} 条，未发送 {skipped_count} 条"
            if failed_count == 0
            else f"补齐完成：成功 {sent_count} 条，未发送 {skipped_count} 条，失败 {failed_count} 条"
        ),
        "requested": requested_limit,
        "processed": len(content_items),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "force": force_send,
        "targets": plan.get("targets", []),
        "results": results,
    }
