"""LINE Messaging API 封裝:推播、回覆,以及審核用的 Flex 卡片。"""
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexBox,
    FlexBubble,
    FlexButton,
    FlexMessage,
    FlexText,
    MessagingApi,
    PostbackAction,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
    URIAction,
)

from .config import get_settings


def _api() -> MessagingApi:
    cfg = Configuration(access_token=get_settings().line_channel_access_token)
    return MessagingApi(ApiClient(cfg))


def reply_text(reply_token: str, text: str) -> None:
    _api().reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))


def push_text(to: str, text: str) -> None:
    _api().push_message(PushMessageRequest(to=to, messages=[TextMessage(text=text)]))


def build_review_flex(batch_id: int, subject: str, preview_line: str) -> FlexMessage:
    """審核卡片:主旨摘要 + 查看完整內容連結 + 三顆動作按鈕。"""
    preview_url = f"{get_settings().public_base_url}/preview/{batch_id}"
    bubble = FlexBubble(
        body=FlexBox(
            layout="vertical",
            spacing="md",
            contents=[
                FlexText(text=f"📩 批次 #{batch_id} 待審核", weight="bold", size="lg"),
                FlexText(text=f"主旨:{subject}", size="sm", wrap=True, color="#333333"),
                FlexText(text=preview_line, size="sm", wrap=True, color="#888888"),
            ],
        ),
        footer=FlexBox(
            layout="vertical",
            spacing="sm",
            contents=[
                FlexButton(
                    style="link",
                    height="sm",
                    action=URIAction(label="🔍 查看完整內容", uri=preview_url),
                ),
                FlexButton(
                    style="primary",
                    height="sm",
                    action=PostbackAction(
                        label="✅ 立即發布", data=f"action=publish&batch={batch_id}", display_text="立即發布"
                    ),
                ),
                FlexButton(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="✏️ 修改", data=f"action=modify&batch={batch_id}", display_text="修改"
                    ),
                ),
                FlexButton(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="🔄 重新生成", data=f"action=regen&batch={batch_id}", display_text="重新生成"
                    ),
                ),
            ],
        ),
    )
    return FlexMessage(alt_text=f"批次 #{batch_id} 待審核:{subject}", contents=bubble)


def push_review(to: str, batch_id: int, subject: str, preview_line: str) -> None:
    _api().push_message(PushMessageRequest(to=to, messages=[build_review_flex(batch_id, subject, preview_line)]))
