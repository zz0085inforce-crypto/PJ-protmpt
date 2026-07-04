"""把批次內容渲染成一頁 HTML,對應 Line 卡片上的『查看完整內容』網址。"""
import html

from .state import Batch

_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>批次 #{bid} 預覽</title>
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", sans-serif; margin: 0; background:#f4f5f7; }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 24px 16px; }}
  .meta {{ color:#888; font-size:13px; margin-bottom:8px; }}
  .subject {{ font-size:20px; font-weight:700; margin:0 0 16px; }}
  .card {{ background:#fff; border-radius:12px; padding:24px; box-shadow:0 1px 4px rgba(0,0,0,.08); }}
  table {{ border-collapse: collapse; }}
</style></head>
<body><div class="wrap">
  <div class="meta">批次 #{bid} · 狀態 {status} · 收件人 {n} 位(此為即將寄出的實際內容)</div>
  <div class="card">
    <p class="subject">{subject}</p>
    <div class="body">{body}</div>
  </div>
</div></body></html>"""


def render_preview(batch: Batch) -> str:
    return _PAGE.format(
        bid=batch.id,
        status=html.escape(batch.status),
        n=len(batch.recipients),
        subject=html.escape(batch.subject or "(無主旨)"),
        body=batch.body_html or "<em>(尚無內容)</em>",  # body_html 由 AI 產生,信任其為 HTML
    )
