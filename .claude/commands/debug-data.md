# debug-data

診斷資料問題：資料庫內容、API 回傳、分析結果。

## 用法
`/debug-data <股票代號>`  或  `/debug-data <描述問題>`

## 你的任務

根據 `$ARGUMENTS` 診斷資料問題。

### 診斷清單（依序執行）

1. **確認資料庫有資料**
   - 查 `institutional_investors` 表：該股票有幾筆、最新日期是哪天
   - 查 `stock_prices` 表：K 線資料是否存在

2. **確認設定正確**
   - 讀 `config/settings.py`，看 API 金鑰和門檻值
   - 讀 `watchlist.txt`，確認股票代號格式

3. **追蹤分析結果**
   - 在 `analysis/institutional_analyzer.py` 找到判斷邏輯
   - 說明為什麼這支股票有/沒有觸發異常

4. **給出診斷報告**
   - 問題根因是什麼
   - 如何修正（給具體的程式碼或操作步驟）
