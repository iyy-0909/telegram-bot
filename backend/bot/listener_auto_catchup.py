import asyncio
import copy
import json

from bot.listener_catchup import (
    MAX_AUTO_CATCHUP_ITEMS,
    build_listener_catchup_plan,
    get_message_text,
)
from bot.logger import logger
from bot.runtime_queue import runtime_queue_state
from bot.sender import cleanup_prepared, prepare_album, prepare_single_message


_active_catchup_tasks = {}


def is_listener_catchup_running(task_id):
    worker = _active_catchup_tasks.get(int(task_id))
    return bool(worker and not worker.done())


def start_listener_catchup_background(task, *, force, limit, queue_item_id):
    task_id = int(task.id)
    if is_listener_catchup_running(task_id):
        return None

    worker = asyncio.create_task(
        run_listener_catchup_background(
            task,
            force=force,
            limit=limit,
            queue_item_id=queue_item_id,
        )
    )
    _active_catchup_tasks[task_id] = worker

    def clear_worker(completed):
        if _active_catchup_tasks.get(task_id) is completed:
            _active_catchup_tasks.pop(task_id, None)

    worker.add_done_callback(clear_worker)
    return worker


def update_catchup_progress(
    queue_item_id,
    *,
    status="running",
    reason="正在执行监听补齐",
    total_count=0,
    processed_count=0,
    sent_count=0,
    skipped_count=0,
    failed_count=0,
):
    if not queue_item_id:
        return

    runtime_queue_state.update_waiting(
        queue_item_id,
        status=status,
        reason=reason,
        total_count=total_count,
        processed_count=processed_count,
        sent_count=sent_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        progress_text=f"{processed_count}/{total_count}",
    )


async def catchup_latest_listener_message(
    task,
    force=True,
    limit=MAX_AUTO_CATCHUP_ITEMS,
    queue_item_id=None,
):
    plan = await build_listener_catchup_plan(task, limit=limit or MAX_AUTO_CATCHUP_ITEMS)

    if not plan.get("ok"):
        if queue_item_id:
            runtime_queue_state.finish(
                queue_item_id,
                success=False,
                error=plan.get("message") or "补齐计划生成失败",
            )
        return plan

    content_items = plan.get("_pending_items") or []
    total_count = len(content_items)
    update_catchup_progress(
        queue_item_id,
        total_count=total_count,
        reason="补齐计划已生成，准备逐条处理",
    )

    if not content_items:
        if queue_item_id:
            runtime_queue_state.finish(queue_item_id, success=True)
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

    for index, item in enumerate(content_items, start=1):
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
            update_catchup_progress(
                queue_item_id,
                total_count=total_count,
                processed_count=index,
                sent_count=sent_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                reason=(
                    f"补齐处理中：成功 {sent_count}，"
                    f"跳过 {skipped_count}，失败 {failed_count}"
                ),
            )

    result = {
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
    if queue_item_id:
        runtime_queue_state.finish(
            queue_item_id,
            success=result["ok"],
            error="" if result["ok"] else result["message"],
        )
    return result


async def run_listener_catchup_background(task, *, force, limit, queue_item_id):
    try:
        return await catchup_latest_listener_message(
            task,
            force=force,
            limit=limit,
            queue_item_id=queue_item_id,
        )
    except asyncio.CancelledError:
        runtime_queue_state.cancel(queue_item_id, "补齐任务被取消")
        raise
    except BaseException as exc:
        runtime_queue_state.finish(
            queue_item_id,
            success=False,
            error=str(exc),
        )
        logger.exception(
            "监听补齐后台任务异常 | "
            f"task_id={task.id} | queue_item_id={queue_item_id} | error={exc}"
        )
        return {
            "ok": False,
            "message": f"补齐任务异常：{exc}",
        }
