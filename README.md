# Line Mail Workflow(Python 骨架)

用 Sheets 整理資料 → Claude 生成信件 → Line Bot 審核(發布 / 修改 / 重新生成)→ 依員編寄給對應同事 → 發信狀態回報 Line。

## 流程

```
POST /batches/start ─► 讀 Sheets 來源列 ─► Claude 生成內容 ─► 存成待審批次
        │
        ▼  push 審核卡片到你的 Line
   [AWAITING_REVIEW]
        ├─ 按「立即發布」► 依員編對照 email ► SMTP 寄送 ► 回寫 Sheets log ► push 發信狀態
        ├─ 按「修改」──► [AWAITING_EDIT] ► 你打字說要改哪 ► Claude 依指示重生 ► 回到待審核
        └─ 按「重新生成」► Claude 重生 ► 回到待審核
```

「修改」是對話式的:按下按鈕後,你下一則**文字訊息**會被當成修改指示。這靠 `user_context` 表記住「你正在改哪一批」,webhook 收到純文字時據此判斷。

## 檔案結構

| 檔案 | 職責 |
|------|------|
| `app/main.py` | FastAPI 進入點:webhook 分流、預覽頁、手動啟動端點 |
| `app/workflow.py` | 編排:start / publish / regenerate / request_modify |
| `app/state.py` | 狀態機常數 + SQLite 持久化(批次、使用者情境) |
| `app/line_client.py` | Line push/reply + 三顆按鈕的審核 Flex 卡片 |
| `app/sheets.py` | 讀來源與員編對照、回寫 log |
| `app/ai.py` | 呼叫 Claude 生成信件(輸出 JSON) |
| `app/mailer.py` | SMTP 逐一寄送、回報每人成敗 |
| `app/preview.py` | 把批次渲染成預覽網頁 |
| `app/config.py` | 從 `.env` 讀設定 |

## 安裝

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入你的金鑰
```

### 需要準備的憑證

1. **LINE**:到 LINE Developers 建一個 Messaging API channel,拿 `Channel access token` 與 `Channel secret`;把你本人的 `userId` 填進 `LINE_ADMIN_USER_IDS`(只有名單內的人能審核、發布)。
2. **Claude**:到 https://console.anthropic.com 取得 API key;模型字串請對照 https://docs.claude.com/en/api/overview 。
3. **Google Sheets**:建立 service account 下載 JSON 金鑰,並把該 service account 的 email 分享進你的試算表(檢視或編輯權限)。
4. **SMTP**:一般公司信箱或 Gmail 應用程式密碼皆可。

## 執行

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Line webhook 需要對外 HTTPS 網址。本機開發可用通道工具:

```bash
# 例如 cloudflared
cloudflared tunnel --url http://localhost:8000
```

把取得的網址 `https://xxx.trycloudflare.com/line/webhook` 填到 LINE channel 的 Webhook URL,並把同一個對外網址設成 `.env` 的 `PUBLIC_BASE_URL`(預覽連結會用它)。

## 觸發一個批次

```bash
curl -X POST http://localhost:8000/batches/start \
  -H "x-start-token: <你的 START_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"source_ref": "1"}'      # 來源分頁的第 1 列資料
```

之後就會收到 Line 審核卡片。

## 要接你自己的資料時,改這幾處

- `app/sheets.py`:三個分頁的欄位假設(來源列格式、員編→email 對照、log 欄位順序)。
- `app/ai.py` 的 `_SYSTEM`:信件語氣、格式、表格規則。
- 觸發方式:目前是手動打 `/batches/start`。若要「Sheet 一有新列就自動跑」,可加 Google Apps Script 的 onEdit 觸發器去打這個端點,或加一個定時掃描的排程。

## 安全備註

- webhook 一律驗證 `X-Line-Signature`。
- 所有審核 / 修改動作都檢查發話者是否在 `LINE_ADMIN_USER_IDS`,避免外人觸發全公司寄信。
- `/batches/start` 用 `START_API_TOKEN` 保護。
- 別把 `.env` 與 service account 金鑰進版控。
