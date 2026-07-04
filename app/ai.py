"""用 Claude 生成信件內容(主旨 + HTML 內文,含表格)。

要求模型只回 JSON,後端安全解析。首次生成 previous_html 為空;
「修改」時把目前內容與使用者的指示一起帶進去,做局部改寫。
"""
import json

import anthropic

from .config import get_settings

_SYSTEM = (
    "你是公司內部通知信的撰寫助手。根據提供的資料產生一封完整的 HTML 信件。"
    "務必只輸出 JSON,格式為 {\"subject\": \"...\", \"body_html\": \"...\"},"
    "不要有任何多餘文字或 markdown 圍欄。body_html 需為可直接寄出的 HTML,"
    "若資料適合以表格呈現,請用 <table> 標籤並加上基本行內樣式。"
)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]  # 去掉可能的語言標記
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def generate_email(source: dict, edit_instruction: str = "", previous_html: str = "") -> dict:
    """回傳 {"subject", "body_html"}。"""
    parts = [f"以下是這封信的來源資料(JSON):\n{json.dumps(source, ensure_ascii=False, indent=2)}"]
    if previous_html and edit_instruction:
        parts.append(f"目前的內文 HTML:\n{previous_html}")
        parts.append(f"請依這個修改指示調整,只改需要改的地方:{edit_instruction}")
    else:
        parts.append("請撰寫這封通知信。")

    resp = _client().messages.create(
        model=get_settings().anthropic_model,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    data = _extract_json(text)
    return {"subject": data.get("subject", "(無主旨)"), "body_html": data.get("body_html", "")}
