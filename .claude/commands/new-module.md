# new-module

新增一個功能模組到這個台股分析專案。

## 用法
`/new-module <模組名稱> <用途描述>`

## 你的任務

根據使用者的 `$ARGUMENTS` 建立一個新模組。

### 專案慣例
- 資料收集放 `collectors/`，分析邏輯放 `analysis/`，通知放 `notifiers/`
- 所有模組要有 `logger = logging.getLogger(__name__)`
- 資料庫操作統一用 `database/db.py` 的 `get_connection()`
- 設定值從 `config/settings.py` 的 `settings` 讀取，不要 hardcode
- 回傳值用 `list[dict]`，dict 的 key 要有 `stock_id`

### 步驟
1. 閱讀 `analysis/institutional_analyzer.py` 了解現有模組結構
2. 閱讀 `config/settings.py` 確認可用的設定
3. 建立新的 `.py` 檔案，遵循現有慣例
4. 在 `main.py` 加入對應的呼叫點（如果適合整合進主流程）
5. 說明新模組的輸入/輸出格式
