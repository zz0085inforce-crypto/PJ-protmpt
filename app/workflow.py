"""流程編排:把 AI、Sheets、寄信、Line 串成狀態機的實際動作。

這些函式多半在 webhook 回覆之後,由 FastAPI 的 BackgroundTasks 執行,
以免 AI 生成或寄信拖太久導致 Line webhook 逾時。
"""
import time

from . import ai, line_client, mailer, sheets, state
from .config import get_settings


def _first_admin() -> str:
    ids = list(get_settings().admin_ids)
    return ids[0] if ids else ""


def _summary_line(body_html: str) -> str:
    """從 HTML 粗略抽一段純文字當 Line 摘要。"""
    import re

    text = re.sub(r"<[^>]+>", " ", body_html)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:60] + "…") if len(text) > 60 else text


def start_batch(source_ref: str, notify_user_id: str = "") -> int:
    """從來源列產生內容,存成待審核批次,並推播審核卡片。回傳 batch_id。"""
    batch = state.create_batch(source_ref)
    source = sheets.get_source_row(source_ref)
    result = ai.generate_email(source)
    recipients = sheets.recipients_from_source(source)
    state.update_batch(
        batch.id,
        status=state.AWAITING_REVIEW,
        subject=result["subject"],
        body_html=result["body_html"],
        recipients=recipients,
    )
    target = notify_user_id or _first_admin()
    if target:
        line_client.push_review(target, batch.id, result["subject"], _summary_line(result["body_html"]))
    return batch.id


def regenerate(batch_id: int, notify_user_id: str, edit_instruction: str = "") -> None:
    """重新生成(重生 or 依修改指示),完成後推播新的審核卡片。"""
    batch = state.get_batch(batch_id)
    if not batch:
        return
    state.update_batch(batch_id, status=state.GENERATING)
    source = sheets.get_source_row(batch.source_ref)
    result = ai.generate_email(
        source,
        edit_instruction=edit_instruction,
        previous_html=batch.body_html if edit_instruction else "",
    )
    state.update_batch(
        batch_id,
        status=state.AWAITING_REVIEW,
        subject=result["subject"],
        body_html=result["body_html"],
    )
    state.clear_user_context(notify_user_id)
    line_client.push_review(notify_user_id, batch_id, result["subject"], _summary_line(result["body_html"]))


def publish(batch_id: int, notify_user_id: str) -> None:
    """發布:寄送 email → 回寫 Sheets → 推播發信狀態。"""
    batch = state.get_batch(batch_id)
    if not batch:
        return
    state.update_batch(batch_id, status=state.SENDING)

    if not batch.recipients:
        state.update_batch(batch_id, status=state.FAILED)
        line_client.push_text(notify_user_id, f"批次 #{batch_id} 沒有可寄送的收件人(員編對照不到 email)。")
        return

    results = mailer.send_html(batch.recipients, batch.subject, batch.body_html)
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    final_status = state.SENT if fail == 0 else state.FAILED
    state.update_batch(batch_id, status=final_status, results=results)

    # 回寫 Sheets 紀錄
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    failed_emails = ",".join(r["email"] for r in results if not r["ok"])
    try:
        sheets.append_log([ts, batch_id, batch.subject, len(results), ok, fail, failed_emails])
    except Exception as e:  # noqa: BLE001
        line_client.push_text(notify_user_id, f"⚠️ 發信完成但寫入 log 失敗:{e}")

    # 推播發信狀態
    msg = f"📊 批次 #{batch_id} 發信完成\n成功 {ok} / 失敗 {fail}(共 {len(results)})"
    if failed_emails:
        msg += f"\n失敗:{failed_emails}"
    line_client.push_text(notify_user_id, msg)


def request_modify(batch_id: int, user_id: str) -> None:
    """使用者按下『修改』:進入等待輸入狀態。"""
    state.update_batch(batch_id, status=state.AWAITING_EDIT)
    state.set_user_context(user_id, batch_id)
