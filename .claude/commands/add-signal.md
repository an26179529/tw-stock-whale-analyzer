# add-signal

新增一個買賣訊號到評分系統。

## 用法
`/add-signal <訊號名稱> <訊號描述>`

例如：
- `/add-signal kd-cross KD 黃金交叉`
- `/add-signal volume-surge 成交量爆量超過均量 1.5 倍`
- `/add-signal margin-decrease 融資連續減少`

## 你的任務

根據 `$ARGUMENTS` 新增一個訊號偵測函式。

### 步驟

1. 閱讀 `analysis/institutional_analyzer.py` 了解現有分析結構
2. 確認這個訊號需要哪些資料欄位（現有資料庫有什麼）
3. 在最適合的分析模組中新增一個私有方法 `_detect_<signal_name>`
4. 方法回傳格式：
   ```python
   {
       "signal": "<訊號名稱>",
       "triggered": True/False,
       "score": 0-30,       # 這個訊號的分數貢獻
       "detail": "人類可讀的說明",
   }
   ```
5. 在現有的 `analyze()` 方法中整合這個訊號
6. 更新 Line 通知模板讓訊號出現在訊息裡

### 訊號評分原則
- 強訊號（主力行為）：20-30 分
- 中訊號（技術面佐證）：10-20 分
- 弱訊號（輔助參考）：5-10 分
