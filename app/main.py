"""FastAPI 進入點。

路由:
  POST /line/webhook   接收 Line 事件(驗簽 → 分流 postback / 文字)
  GET  /preview/{id}   渲染批次預覽頁(Line 卡片的檢視網址)
  POST /batches/start  手動觸發一個批次(需帶 token)
  GET  /health         健康檢查
"""
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

from . import line_client, preview, state, workflow
from .config import get_settings

app = FastAPI(title="Line Mail Workflow")


@app.on_event("startup")
def _startup() -> None:
    state.init_db()


def _is_admin(user_id: str) -> bool:
    return user_id in get_settings().admin_ids


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/preview/{batch_id}", response_class=HTMLResponse)
def preview_page(batch_id: int):
    batch = state.get_batch(batch_id)
    if not batch:
        raise HTTPException(404, "查無此批次")
    return HTMLResponse(preview.render_preview(batch))


@app.post("/batches/start")
def start(payload: dict, background: BackgroundTasks, x_start_token: str = Header(default="")):
    if x_start_token != get_settings().start_api_token:
        raise HTTPException(401, "token 錯誤")
    source_ref = str(payload.get("source_ref", "")).strip()
    if not source_ref:
        raise HTTPException(400, "缺少 source_ref")
    notify = str(payload.get("notify_user_id", "")).strip()
    background.add_task(workflow.start_batch, source_ref, notify)
    return {"queued": True, "source_ref": source_ref}


@app.post("/line/webhook")
async def webhook(request: Request, background: BackgroundTasks, x_line_signature: str = Header(default="")):
    body = (await request.body()).decode("utf-8")
    parser = WebhookParser(get_settings().line_channel_secret)
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(400, "簽章驗證失敗")

    for event in events:
        user_id = getattr(event.source, "user_id", None)

        # ── 按鈕(postback):發布 / 修改 / 重生 ──
        if isinstance(event, PostbackEvent):
            if not user_id or not _is_admin(user_id):
                line_client.reply_text(event.reply_token, "你沒有審核權限。")
                continue
            data = {k: v[0] for k, v in parse_qs(event.postback.data).items()}
            action = data.get("action")
            batch_id = int(data.get("batch", 0))

            if action == "publish":
                line_client.reply_text(event.reply_token, f"批次 #{batch_id} 開始寄送…")
                background.add_task(workflow.publish, batch_id, user_id)
            elif action == "modify":
                workflow.request_modify(batch_id, user_id)
                line_client.reply_text(event.reply_token, "請直接輸入你要修改的地方(例如:開頭改正式一點、表格加總計列)。")
            elif action == "regen":
                line_client.reply_text(event.reply_token, f"批次 #{batch_id} 重新生成中…")
                background.add_task(workflow.regenerate, batch_id, user_id, "")
            continue

        # ── 純文字:可能是修改指示 ──
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            if not user_id or not _is_admin(user_id):
                continue  # 非管理員的訊息直接忽略
            pending = state.get_user_context(user_id)
            if pending:
                line_client.reply_text(event.reply_token, f"收到,依你的指示重新生成批次 #{pending}…")
                background.add_task(workflow.regenerate, pending, user_id, event.message.text)
            else:
                line_client.reply_text(
                    event.reply_token,
                    "目前沒有待修改的批次。收到新批次的審核卡片後,可按『修改』再輸入指示。",
                )
            continue

    return JSONResponse({"ok": True})
