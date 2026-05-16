# security-check

在任何提交、分享程式碼、或部署前，執行完整的資安審查。
**這個 skill 的核心原則：敏感資訊絕對不能出現在公開場合。**

## 用法
`/security-check`           — 全專案掃描
`/security-check <檔案路徑>` — 單檔審查

## 你必須做的事（按順序）

### 1. 掃描硬編碼的敏感資訊

搜尋以下模式，任何一個命中都是高風險：
- API key 模式：`sk-`, `Bearer `, `token =`, `api_key =`, `API_KEY`
- 密碼模式：`password =`, `passwd`, `secret =`, `SECRET`
- 台灣常見 token：FinMind token, Line Channel Access Token, OpenAI key
- 資料庫連線字串帶帳號密碼
- 任何長度超過 20 字的英數混合字串直接寫在 `.py` 檔內

**如果找到：立刻停止，報告位置，禁止繼續任何會讓程式碼公開的操作。**

### 2. 檢查 .gitignore

確認以下項目都在 `.gitignore` 裡：
```
.env
.env.*
*.env
*.pem
*.key
*secret*
*credential*
```
如果少了任何一個，立刻補上。

### 3. 掃描 git 暫存區

執行等效於以下的檢查：
- `git diff --cached` — 看將要提交的內容有無敏感資訊
- `git status` — 確認 `.env` 沒有被 stage

**如果 `.env` 在 staged files 裡：立刻警告，禁止繼續 commit。**

### 4. 掃描 git 歷史（快速）

搜尋最近 10 筆 commit 有無誤提交敏感資訊：
- 檔案名稱包含 `.env`, `secret`, `credential`
- commit 內容包含 API key 模式

如果歷史有問題，提示用 `git filter-repo` 清除，並說明步驟。

### 5. 檢查 logs 和 output 目錄

`output/` 目錄下的檔案不應包含：
- API key 或 token
- 個人識別資訊（Line user ID、真實姓名、手機）

### 6. 檢查程式碼中的 print/logging

確認沒有把以下內容印出到 console 或寫入 log 檔：
- `settings.finmind_token`
- `settings.openai_api_key`
- `settings.line_channel_access_token`
- 任何帶 `token`, `key`, `secret` 字樣的變數值

---

## 報告格式

最後輸出一份審查報告：

```
=== 資安審查報告 ===

✅ 通過項目
- .gitignore 設定完整
- 無硬編碼 API key

❌ 風險項目（必須修正）
- [檔案:行號] 說明問題

⚠️  建議改善
- 說明非緊急但應改進的地方

結論：[通過 / 需修正後才能提交]
```

---

## 絕對禁止的行為

這個 skill 執行過程中，你**絕對不能**：
- 把任何 `.env` 的內容貼到對話裡
- 把 API key、token、密碼輸出到任何地方
- 建議把 secret 寫進程式碼「暫時用一下」
- 跳過任何一個檢查步驟
