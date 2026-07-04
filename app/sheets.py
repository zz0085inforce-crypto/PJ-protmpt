"""Google Sheets 存取層(gspread)。

假設的分頁結構(欄位名稱都可在 .env 調整):
  - source    :每一列是一個候選批次;含生成用的欄位,以及一個「員編」欄(逗號分隔多個員編)
  - employees :員編 ↔ email 對照
  - log       :寄信結果會 append 到這裡

gspread 用 service account 認證,記得把 service account 的 email 分享進試算表。
"""
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

from .config import get_settings

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@lru_cache
def _client() -> gspread.Client:
    s = get_settings()
    creds = Credentials.from_service_account_file(s.google_service_account_file, scopes=_SCOPES)
    return gspread.authorize(creds)


def _sheet(tab: str):
    return _client().open_by_key(get_settings().spreadsheet_id).worksheet(tab)


def get_source_row(row_ref: str) -> dict:
    """row_ref 為來源分頁的列號(1-based 資料列,不含標題)。回傳 欄名->值 的 dict。"""
    s = get_settings()
    records = _sheet(s.source_sheet).get_all_records()  # list[dict],已用第一列當標題
    idx = int(row_ref) - 1
    if idx < 0 or idx >= len(records):
        raise IndexError(f"來源分頁找不到第 {row_ref} 列資料")
    return records[idx]


def resolve_recipients(emp_ids: list[str]) -> list[str]:
    """把員編清單對照成 email 清單(找不到的會被略過)。"""
    s = get_settings()
    records = _sheet(s.employee_sheet).get_all_records()
    mapping = {
        str(r[s.employee_id_column]).strip(): str(r[s.employee_email_column]).strip()
        for r in records
        if r.get(s.employee_id_column) and r.get(s.employee_email_column)
    }
    out = []
    for eid in emp_ids:
        email = mapping.get(str(eid).strip())
        if email:
            out.append(email)
    return out


def recipients_from_source(row: dict) -> list[str]:
    """從來源列取出員編欄(逗號分隔)→ 解析成 email。"""
    raw = str(row.get(get_settings().source_recipients_column, "")).strip()
    emp_ids = [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
    return resolve_recipients(emp_ids)


def append_log(values: list) -> None:
    _sheet(get_settings().log_sheet).append_row(values, value_input_option="USER_ENTERED")
